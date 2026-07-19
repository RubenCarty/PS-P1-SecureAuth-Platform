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
    return redirect(url_for("index"))

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
    users = conn.execute("SELECT id, email, role FROM users").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template("admin.html", users=users, products=products)

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
            "INSERT INTO products (name, description, price, image_url) VALUES (?, ?, ?, ?)",
            (form.name.data, form.description.data, form.price.data, image_filename),
        )
        conn.commit()
        conn.close()
        flash("Producto creado correctamente.", "success")
        return redirect(url_for("admin_panel"))
    return render_template("admin_product_new.html", form=form)

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
    purchases = conn.execute(
        "SELECT * FROM purchases WHERE user_id = ? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    
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
            ("ana.rodriguez@outlook.es", "AnaSecure#2026", "user"),
            ("miguel.torres@outlook.com", "Miguel@Secure2026", "user"),
            ("lucia.fernandez@outlook.es", "LuciaSecure2026$", "user"),
            ("jose.ramirez@outlook.com", "Jose#Secure2026!", "user")
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
            ("Router SecureEdge", "Router empresarial con firewall avanzado y actualizaciones seguras.", 460, "router.jpg", "Electrónica", 20),
            ("Cámara IP SafeCam", "Cámara con cifrado extremo a extremo y alertas inteligentes.", 310, "camaras.jpg", "Electrónica", 35),
            ("Camiseta SecurityOps", "Camiseta premium con diseño de código binario y logo de seguridad.", 45, "camiseta.jpg", "Ropa", 100),
            ("Hoodie ZeroTrust", "Sudadera térmica con diseño minimalista y parche RBAC.", 90, "hoodie.jpg", "Ropa", 60),
            ("Gorra Authenticator", "Gorra ligera con bordado de clave de autenticación.", 28, "gorra.jpg", "Ropa", 120),
            ("Polo ThreatIntel", "Polo con tecnología de tejido antiestática.", 55, "polo.jpg", "Ropa", 80),
            ("Lámpara ZeroTrust", "Lámpara inteligente con autenticación biométrica.", 250, "lampara.jpg", "Hogar", 15),
            ("Cerradura SmartSafe", "Cerradura inteligente con registro de accesos y cifrado.", 190, "cerradura.jpg", "Hogar", 25),
            ("Sensor de Movimiento Guard", "Sensor con detección avanzada y alertas en tiempo real.", 65, "sensor.jpg", "Hogar", 90),
            ("Alarma SecureHome", "Sistema de alarma para hogar con panel cifrado.", 420, "alarma.jpg", "Hogar", 10),
            ("Zapatillas EncryptRun", "Zapatillas para running con suela antibloqueo y conectividad.", 180, "zapatillas.jpg", "Deportes", 30),
            ("Mochila VaultPack", "Mochila resistente al agua con compartimento seguro.", 120, "mochila.jpg", "Deportes", 22),
            ("Botella HidrateShield", "Botella térmica con tapa a prueba de fugas.", 35, "botella.jpg", "Deportes", 150),
            ("Guantes ActiveSecure", "Guantes con agarre antideslizante para entrenamientos.", 40, "guantes.jpg", "Deportes", 80),
            ("Libro Ciberseguridad Avanzada", "Guía completa de seguridad empresarial moderna.", 75, "libro.jpg", "Libros", 200),
            ("Manual de Criptografía Práctica", "Introducción y ejercicios para criptografía aplicada.", 110, "criptografia.jpg", "Libros", 140),
            ("Guía de DevSecOps", "Patrones y prácticas para integrar seguridad en CI/CD.", 98, "devsecops.jpg", "Libros", 160),
            ("Libro OSINT en Acción", "Casos y metodología para análisis OSINT.", 85, "osint.jpg", "Libros", 180),
            ("Tarjeta Regalo SecureVault", "Tarjeta regalo para comprar productos en SecureVault Commerce.", 60, "giftcard.jpg", "Otros", 300),
            ("Kit de Inicio Passwords", "Kit educativo con plantillas y guías de contraseñas.", 25, "kit.jpg", "Otros", 500),
            ("Accesorio CableShield", "Organizador de cables con material resistente al desgaste.", 18, "cables.jpg", "Otros", 400),
            ("Plantilla Auditoría Express", "Plantilla imprimible para auditoría básica de seguridad.", 12, "plantilla.jpg", "Otros", 600)
        ])
        print("Productos de prueba inyectados correctamente.")
        
    conn.commit()
    conn.close()


# AUTOMATIZACIÓN SEGURA: Inicializa la base de datos al arrancar la app si el archivo no existe
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
