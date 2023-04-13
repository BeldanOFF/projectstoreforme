import os
import random

from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_admin import Admin, form
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import Select2Field
from flask_admin.model import InlineFormAdmin
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
app.config['SECRET_KEY'] = 'super secret key'
app.config['STORAGE'] = 'static/products_img/'
login_manager = LoginManager()
login_manager.init_app(app)

db = SQLAlchemy(app)


class Catalog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    products = db.relationship('Product', backref='catalog', lazy=True)
    image = db.Column(db.String(255))


class Collections(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    products = db.relationship('Product', backref='collections', lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)
    description = db.Column(db.String(255))
    count_available = db.Column(db.Integer)
    image = db.Column(db.String(255))
    catalog_id = db.Column(db.Integer, db.ForeignKey('catalog.id'))
    collection_id = db.Column(db.Integer, db.ForeignKey('collections.id'))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'


class StorageAdminModel(ModelView):
    form_extra_fields = {
        'file': form.FileUploadField('file')
    }

    def _change_path_data(self, _form):
        try:
            storage_file = _form.file.data

            if storage_file is not None:
                hash = random.getrandbits(128)
                ext = storage_file.filename.split('.')[-1]
                path = '%s.%s' % (hash, ext)

                storage_file.save(
                    os.path.join(app.config['STORAGE'], path)
                )

                _form.image.data = path

                del _form.file

        except Exception as ex:
            pass

        return _form

    def edit_form(self, obj=None):
        return self._change_path_data(
            super(StorageAdminModel, self).edit_form(obj)
        )

    def create_form(self, obj=None):
        return self._change_path_data(
            super(StorageAdminModel, self).create_form(obj)
        )


class ProductAdminModel(StorageAdminModel):
    form_extra_fields = {
        'catalog_id': Select2Field('Catalog', choices=[]),
        'collection_id': Select2Field('Collection', choices=[]),
        'file': form.FileUploadField('file')
    }

    def _change_path_data(self, _form):
        try:
            storage_file = _form.file.data

            if storage_file is not None:
                hash = random.getrandbits(128)
                ext = storage_file.filename.split('.')[-1]
                path = '%s.%s' % (hash, ext)

                storage_file.save(
                    os.path.join(app.config['STORAGE'], path)
                )

                _form.image.data = path

                del _form.file

        except Exception as ex:
            pass

        return _form

    def create_form(self, obj=None):
        form = super(ProductAdminModel, self).create_form(obj=obj)
        form.collection_id.choices = [(c.id, c.title) for c in Collections.query.all()]
        form.catalog_id.choices = [(c.id, c.title) for c in Catalog.query.all()]
        return form

    def edit_form(self, obj=None):
        form = super(StorageAdminModel, self).edit_form(obj=obj)
        form.collection_id.choices = [(c.id, c.title) for c in Collections.query.all()]
        return form


class UserView(ModelView):
    form_columns = ('name', 'email')


class CollectionView(ModelView):
    form_columns = ('title', 'products')


admin = Admin(app, name='Online Store Admin Panel')
admin.add_view(ProductAdminModel(Product, db.session))
admin.add_view(StorageAdminModel(Catalog, db.session))
admin.add_view(CollectionView(Collections, db.session))
admin.add_view(UserView(User, db.session))


@app.route('/')
@app.route('/index')
def index():
    collections = Collections.query.order_by(Collections.title).all()
    catalog = Catalog.query.order_by(Catalog.title).all()
    items = Product.query.order_by(Product.price).all()

    return render_template('index.html', collections=collections, catalog=catalog)


@app.route('/info')
def info():
    return render_template('info.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        # Проверяем, что все поля заполнены
        if not name or not email or not password:
            return 'Заполните все поля'

        # Проверяем, что пользователь с таким email уже не зарегистрирован
        if User.query.filter_by(email=email).first():
            return 'Пользователь с таким email уже зарегистрирован'

        # Создаем нового пользователя
        user = User(name=name, email=email, password=password_hash)

        # Добавляем пользователя в базу данных
        db.session.add(user)
        db.session.commit()

        return 'Регистрация прошла успешно!'
    else:
        return render_template('register.html')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/catalog/<int:catalog_id>/product/<int:product_id>')
def product_page(catalog_id, product_id):
    catalogs = catalog_id
    product = Product.query.get(product_id)
    if product is None:
        abort(404)
    return render_template('product.html', product=product, catalog_id=catalogs)


@app.route('/userlogin', methods=['GET', 'POST'])
def userlogin():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']

        # Find user by email
        user = User.query.filter_by(email=email).first()

        if not user or not user.password or not user.password.startswith('pbkdf2:sha256:'):
            # Invalid email or password hash format
            flash('Invalid email or password')
            return redirect(url_for('userlogin'))

        if check_password_hash(user.password, password):
            # Password is correct, login the user
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        else:
            # Password is incorrect
            flash('Invalid email or password')
            return redirect(url_for('userlogin'))
    else:
        return render_template('userlogin.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# Обработчик запроса на авторизацию
@app.route('/adminlogin', methods=['GET', 'POST'])
def adminlogin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверяем, что логин и пароль корректны
        if username == 'admin' and password == 'password':
            # Создаем сессию для администратора
            session['logged_in'] = True
            return redirect(url_for('admin.index'))

    return render_template('adminlogin.html')


# Декоратор для проверки авторизации администратора
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('adminlogin'))
        return f(*args, **kwargs)

    return decorated_function


# Защищенный ресурс, доступный только для администраторов
@app.route('/admin')
@admin_login_required
def admin():
    return redirect(url_for('admin.index'))



@app.route('/catalog')
def catalog():
    category = request.args.get('category')
    collections = Catalog.query.order_by(Catalog.title).all()
    if category:
        catalog = Catalog.query.filter_by(category=category).order_by(Catalog.title).all()
    else:
        catalog = Catalog.query.order_by(Catalog.title).all()
    return render_template('catalog odej.html', collections=collections, catalog=catalog)


@app.route('/catalog/<int:catalog_id>')
def catalog_tag(catalog_id):
    catalogs = Catalog.query.get(catalog_id)
    if catalogs is None:
        abort(404)
    collections = request.args.getlist('collection')
    collection = Collections.query.order_by(Collections.id).all()
    if not collections:
        product = Product.query.filter(Product.catalog_id == catalog_id).order_by(Product.name).all()
    else:
        product = Product.query.filter(Product.catalog_id == catalog_id, Product.collection_id.in_(collections)).all()
    return render_template('catalog.html', product=product, collection=collection, collections=collections, catalog_id=catalog_id)



if __name__ == '__main__':
    app.run(debug=True)
