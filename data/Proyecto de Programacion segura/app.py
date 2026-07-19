import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort, jsonify
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FileField, HiddenField, SelectField
from wtforms.validators import DataRequired, Length, Email, NumberRange
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from datetime import timedelta
import sqlite3
import uuid
from datetime import datetime

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "change_me_secret"),
    SESSION_COOKIE_SECURE=True,
    REMEMBER_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
)

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["20 per minute"])

oauth = OAuth(app)

CLIENT_ID = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
TENANT_ID = os.environ.get("AZURE_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

if CLIENT_ID and CLIENT_SECRET and TENANT_ID:
    oauth.register(
        name="microsoft",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        server_metadata_url=f"{AUTHORITY}/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email offline_access"},
    )

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
UPLOAD_FOLDER = os.path.join(app.instance_path, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

DATABASE = os.path.join(app.instance_path, "secureauth.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

class User(UserMixin):
    def __init__(self, id_, email, role="user"):
        self.id = id_
        self.email = email
        self.role = role

    def get_id(self):
        return str(self.id)

    def is_admin(self):
        return self.role == "admin"

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user["id"], user["email"], user["role"])
    return None

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Iniciar sesión")

class ProductForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=120)])
    description = StringField("Descripción", validators=[DataRequired(), Length(max=500)])
    price = IntegerField("Precio", validators=[DataRequired(), NumberRange(min=0)])
    category = SelectField("Categoría", choices=[("Electrónica", "Electrónica"), ("Ropa", "Ropa"), ("Hogar", "Hogar"), ("Deportes", "Deportes"), ("Libros", "Libros"), ("Otros", "Otros")], validators=[DataRequired()])
    stock = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0)], default=1)
    image = FileField("Imagen")
    submit = SubmitField("Guardar")

class CartItemForm(FlaskForm):
    product_id = HiddenField("product_id", validators=[DataRequired()])
    quantity = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=1, max=20)])
    submit = SubmitField("Agregar al carrito")

class CheckoutForm(FlaskForm):
    payment_method = SelectField("Método de pago", choices=[("yape", "Yape"), ("visa", "Visa"), ("mastercard", "Mastercard")], validators=[DataRequired()])
    phone = StringField("Celular", validators=[Length(max=15)])
    card_holder = StringField("Titular", validators=[Length(max=100)])
    card_number = StringField("Número", validators=[Length(max=19)])
    card_expiry = StringField("Vencimiento", validators=[Length(max=5)])
    card_cvv = StringField("CVV", validators=[Length(max=4)])
    submit = SubmitField("Finalizar compra")

@app.before_request
def enforce_https_and_security_headers():
    if request.is_secure is False and os.environ.get("FLASK_ENV") == "production":
        return redirect(request.url.replace("http://", "https://"), code=301)
    return None


@app.after_request
def set_security_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self' https://login.microsoftonline.com"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


@app.route("/")
@limiter.limit("20 per minute")
def index():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template("index.html", products=products)

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (form.email.data,)).fetchone()
        conn.close()
        if user and form.password.data == user["password"]:
            user_obj = User(user["id"], user["email"], user["role"])
            login_user(user_obj)
            return redirect(url_for("index"))
        flash("Credenciales inválidas.", "danger")
    return render_template("login.html", form=form)

@app.route("/login/microsoft")
@limiter.limit("10 per minute")
def login_microsoft():
    if "microsoft" not in oauth._clients:
        flash("OAuth no configurado.", "warning")
        return redirect(url_for("login"))
    redirect_uri = url_for("authorize", _external=True, _scheme="https")
    return oauth.microsoft.authorize_redirect(redirect_uri)

@app.route("/authorize")
@limiter.limit("10 per minute")
def authorize():
    token = oauth.microsoft.authorize_access_token()
    user_info = oauth.microsoft.parse_id_token(token)
    email = user_info.get("email") or user_info.get("preferred_username")
    if not email:
        flash("No se pudo obtener el correo de Microsoft.", "danger")
        return redirect(url_for("login"))

    allowed_suffixes = ("outlook.es", "outlook.com")
    email_lower = email.strip().lower()
    if not email_lower.endswith(allowed_suffixes):
        flash("Acceso denegado: solo se permiten correos outlook.es y outlook.com.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email_lower,)).fetchone()
    if not user:
        conn.execute(
            "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
            (email_lower, "", "user"),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email_lower,)).fetchone()
    conn.close()

    user_obj = User(user["id"], user["email"], user["role"])
    login_user(user_obj)
    return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/product/<int:product_id>")
@limiter.limit("20 per minute")
def product_detail(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not product:
        abort(404)
    cart_form = CartItemForm(product_id=product_id, quantity=1)
    return render_template("product.html", product=product, cart_form=cart_form)

@app.route("/cart", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute")
def cart():
    cart = session.get("cart", {})
    conn = get_db_connection()
    product_ids = tuple(cart.keys())
    products = []
    if product_ids:
        query = f"SELECT * FROM products WHERE id IN ({','.join('?' for _ in product_ids)})"
        products = conn.execute(query, tuple(product_ids)).fetchall()
    conn.close()
    cart_items = []
    total = 0
    for product in products:
        quantity = cart.get(str(product["id"]), 0)
        subtotal = product["price"] * quantity
        total += subtotal
        cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    return render_template("cart.html", cart_items=cart_items, total=total)

@app.route("/cart/add", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def add_to_cart():
    form = CartItemForm()
    if form.validate_on_submit():
        cart = session.setdefault("cart", {})
        product_id = str(form.product_id.data)
        cart[product_id] = min(cart.get(product_id, 0) + form.quantity.data, 20)
        session["cart"] = cart
        flash("Producto agregado al carrito.", "success")
    else:
        flash("No se pudo añadir el producto.", "danger")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart/update/<int:product_id>", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def update_cart(product_id):
    cart = session.get("cart", {})
    pid = str(product_id)
    quantity = request.form.get("quantity", type=int)
    if quantity is None or quantity < 1:
        quantity = 1
    quantity = min(quantity, 20)
    cart[pid] = quantity
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    pid = str(product_id)
    if pid in cart:
        del cart[pid]
        session["cart"] = cart
        flash("Producto eliminado del carrito.", "success")
    return redirect(url_for("cart"))

@app.route("/admin")
@login_required
@limiter.limit("10 per minute")
def admin_panel():
    if not current_user.is_admin():
        abort(403)
    conn = get_db_connection()
    users_raw = conn.execute("SELECT * FROM users").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    purchases = conn.execute("SELECT * FROM purchases").fetchall()
    audit_logs = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    
    users = []
    for u in users_raw:
        user_purchases = [p for p in purchases if p["user_id"] == u["id"]]
        users.append({
            "id": u["id"],
            "email": u["email"],
            "role": u["role"],
            "total_purchases": len(user_purchases),
            "total_spent": sum(p["total"] for p in user_purchases)
        })
    
    return render_template("admin.html", users=users, products=products, purchases=purchases, audit_logs=audit_logs)

@app.route("/admin/product/new", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute")
def admin_product_new():
    if not current_user.is_admin():
        abort(403)
    form = ProductForm()
    if form.validate_on_submit():
        image_filename = None
        image = form.image.data
        if image:
            filename = secure_filename(image.filename)
            extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if extension not in ALLOWED_EXTENSIONS:
                flash("Tipo de archivo no permitido.", "danger")
                return redirect(request.url)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(filepath)
            image_filename = filename
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO products (name, description, price, image_url, category, stock) VALUES (?, ?, ?, ?, ?, ?)",
            (form.name.data, form.description.data, form.price.data, image_filename, form.category.data, form.stock.data),
        )
        conn.commit()
        conn.close()
        log_audit(actor=current_user.email, action="product_created", metadata=f"Created: {form.name.data}")
        flash("Producto creado correctamente.", "success")
        return redirect(url_for("admin_panel"))
    return render_template("admin_product_new.html", form=form)

@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def admin_product_delete(product_id):
    if not current_user.is_admin():
        abort(403)
    conn = get_db_connection()
    product = conn.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    log_audit(actor=current_user.email, action="product_deleted", metadata=f"Deleted: {product['name'] if product else product_id}")
    flash("Producto eliminado.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def admin_change_role(user_id):
    if not current_user.is_admin():
        abort(403)
    new_role = request.form.get("role")
    if new_role not in ("user", "admin"):
        abort(400)
    conn = get_db_connection()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()
    flash("Rol de usuario actualizado.", "success")
    return redirect(url_for("admin_panel"))

def log_audit(actor, action, metadata="", ip=None):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (actor, action, metadata, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
        (actor, action, metadata, ip or request.remote_addr, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def send_admin_email(subject, html_content):
    admin_email = "carlos.mendoza.92@outlook.com"
    print(f"[EMAIL] To: {admin_email}, Subject: {subject}")
    print(f"[EMAIL] Content: {html_content[:200]}...")

@app.route("/checkout", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute")
def checkout():
    form = CheckoutForm()
    cart = session.get("cart", {})
    conn = get_db_connection()
    product_ids = tuple(cart.keys())
    products = []
    if product_ids:
        query = f"SELECT * FROM products WHERE id IN ({','.join('?' for _ in product_ids)})"
        products = conn.execute(query, tuple(product_ids)).fetchall()
    conn.close()
    
    cart_items = []
    total = 0
    for product in products:
        quantity = cart.get(str(product["id"]), 0)
        subtotal = product["price"] * quantity
        total += subtotal
        cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    
    if not cart_items:
        return render_template("checkout.html", cart_items=[], total=0, form=form, show_success=False)
    
    if form.validate_on_submit():
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        payment_detail = ""
        if form.payment_method.data == "yape":
            payment_detail = f"Celular: {form.phone.data}"
        elif form.payment_method.data == "visa":
            payment_detail = f"Tarjeta: ****-****-****-{form.card_number.data[-4:] if form.card_number.data else '****'}"
        elif form.payment_method.data == "mastercard":
            payment_detail = f"Tarjeta: ****-****-****-{form.card_number.data[-4:] if form.card_number.data else '****'}"
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO purchases (order_number, user_id, total, payment_method, payment_detail, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_number, current_user.id, total, form.payment_method.data, payment_detail, "completed", datetime.now().isoformat())
        )
        purchase_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        for item in cart_items:
            conn.execute(
                "INSERT INTO purchase_items (purchase_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (purchase_id, item["product"]["id"], item["quantity"], item["product"]["price"])
            )
        conn.commit()
        conn.close()
        
        log_audit(
            actor=current_user.email,
            action="purchase_completed",
            metadata=f"Order: {order_number}, Total: {total}, Method: {form.payment_method.data}"
        )
        
        email_html = f"""
        <h2>Nueva compra completada</h2>
        <p><strong>Orden:</strong> {order_number}</p>
        <p><strong>Cliente:</strong> {current_user.email}</p>
        <p><strong>Total:</strong> ${total/100:.2f}</p>
        <p><strong>Método:</strong> {form.payment_method.data.title()}</p>
        """
        send_admin_email("Nueva compra - SECUREAUTH", email_html)
        
        session.pop("cart", None)
        return render_template("checkout.html", 
            cart_items=cart_items, 
            total=total, 
            order_number=order_number, 
            payment_method=form.payment_method.data,
            show_success=True,
            created_at=datetime.now().strftime("%d/%m/%Y %H:%M"))
    
    return render_template("checkout.html", cart_items=cart_items, total=total, form=form, show_success=False)

@app.route("/perfil")
@login_required
@limiter.limit("20 per minute")
def perfil():
    conn = get_db_connection()
    purchases_raw = conn.execute(
        "SELECT * FROM purchases WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    
    purchases = []
    for p in purchases_raw:
        items = conn.execute(
            "SELECT pi.*, pr.name FROM purchase_items pi JOIN products pr ON pi.product_id = pr.id WHERE pi.purchase_id = ?",
            (p["id"],)
        ).fetchall()
        items_summary = ", ".join([f"{i['name']} × {i['quantity']}" for i in items])
        purchases.append({**dict(p), "items_summary": items_summary})
    
    total_purchases = len(purchases)
    total_spent = sum(p["total"] for p in purchases)
    pending_count = sum(1 for p in purchases if p["status"] != "completed")
    
    yape_count = sum(1 for p in purchases if p["payment_method"] == "yape")
    yape_total = sum(p["total"] for p in purchases if p["payment_method"] == "yape")
    visa_count = sum(1 for p in purchases if p["payment_method"] == "visa")
    visa_total = sum(p["total"] for p in purchases if p["payment_method"] == "visa")
    mc_count = sum(1 for p in purchases if p["payment_method"] == "mastercard")
    mc_total = sum(p["total"] for p in purchases if p["payment_method"] == "mastercard")
    conn.close()
    conn.close()
    
    return render_template("perfil.html",
        total_purchases=total_purchases,
        total_spent=total_spent,
        pending_count=pending_count,
        yape_count=yape_count, yape_total=yape_total,
        visa_count=visa_count, visa_total=visa_total,
        mc_count=mc_count, mc_total=mc_total,
        purchases=purchases)

@app.route("/mis-compras")
@login_required
@limiter.limit("20 per minute")
def mis_compras():
    conn = get_db_connection()
    purchases = conn.execute(
        "SELECT * FROM purchases WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    conn.close()
    
    return render_template("mis-compras.html", purchases=purchases)

@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.cli.command("init-db")
def init_db_command():
    """Comando de consola para inicializar la base de datos de forma manual."""
    init_db()
    print("Base de datos inicializada de forma manual.")

def init_db():
    """Crea las tablas e inyecta productos de prueba si no existen."""
    os.makedirs(app.instance_path, exist_ok=True)
    
    conn = get_db_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price INTEGER NOT NULL,
        image_url TEXT,
        category TEXT DEFAULT 'Otros',
        stock INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        total INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        payment_detail TEXT,
        status TEXT NOT NULL DEFAULT 'completed',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price INTEGER NOT NULL,
        FOREIGN KEY (purchase_id) REFERENCES purchases (id)
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        metadata TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
    """)
    
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        test_users = [
            ("carlos.mendoza.92@outlook.com", "C4rl0s!2026Mx", "admin"),
            ("valeria.rojas.g@outlook.com", "V4leria#Secure88", "user"),
            ("diego.ramirez.dev@outlook.es", "D13go$Pass2026", "user"),
            ("sofia.torres.lima@outlook.es", "S0fia!Cloud947", "user"),
            ("andres.garcia.tech@outlook.es", "Andr3s#Net2026", "user")
        ]
        for email, pwd, role in test_users:
            conn.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)", (email, pwd, role))
        print("Usuarios de prueba inyectados correctamente.")

    cursor = conn.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        conn.executemany("""
            INSERT INTO products (name, description, price, image_url, category, stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("Token de Autenticación FIDO2", "Llave física criptográfica para MFA resistente al phishing.", 850, "token.jpg", "Electrónica", 25),
            ("Software Antimalware Enterprise", "Licencia anual para protección de endpoints con IA.", 1200, "antivirus.jpg", "Electrónica", 50),
            ("Camiseta SecurityOps", "Camiseta premium con diseño de código binario y logo de seguridad.", 45, "camiseta.jpg", "Ropa", 100),
            ("Zapatillas EncryptRun", "Zapatillas para running con suela antibloqueo y Bluetooth.", 180, "zapatillas.jpg", "Deportes", 30),
            ("Lámpara ZeroTrust", "Lámpara inteligente con autenticación biométrica.", 250, "lampara.jpg", "Hogar", 15),
            ("Libro Ciberseguridad Avanzada", "Guía completa de seguridad empresarial moderna.", 75, "libro.jpg", "Libros", 200),
            ("Auriculares Firewall Pro", "Auriculares con cancellación de ruido y micrófon activo.", 320, "auriculares.jpg", "Electrónica", 40),
            ("Soporte Seguridad Web", "Licencia anual para CDN con protección DDoS.", 450, "soporte.jpg", "Electrónica", 100),
            ("Pantalón HackerFit", "Pantalón cómodo para largas sesiones de código.", 85, "pantalon.jpg", "Ropa", 75),
            ("Mochila SecurePack", "Mochila con compuerto oculto y protección RFID.", 120, "mochila.jpg", "Deportes", 60),
            ("Taza EncryptJoy", "Taza de cerámica con mensaje criptográfico.", 25, "taza.jpg", "Hogar", 150),
            ("Termo DataSafe", "Termo inteligente con app de control de temperatura.", 65, "termo.jpg", "Hogar", 80),
            ("Pelota Pentest Pro", "Pelota de gimnasio para estresaje de seguridad.", 40, "pelota.jpg", "Deportes", 90),
            ("Mouse ClickSecure", "Mouse ergonómico con botón de pánico integrado.", 95, "mouse.jpg", "Electrónica", 200),
            ("Teclado QuantumKey", "Teclado mecánico con switches criptográficos.", 280, "teclado.jpg", "Electrónica", 35),
            ("Guantes BlueLight", "Guantes táctiles para reducir fatiga digital.", 55, "guantes.jpg", "Otros", 120)
        ])
        print("Productos de prueba inyectados correctamente.")
        
    conn.commit()
    conn.close()


# AUTOMATIZACIÓN SEGURA: Inicializa la base de datos al arrancar la app si el archivo no existe
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
