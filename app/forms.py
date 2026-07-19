from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
)


class LoginForm(FlaskForm):
    email = StringField(
        "Correo electrónico",
        validators=[
            DataRequired(),
            Email(),
            Length(max=254),
        ],
    )

    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired(),
            Length(min=8, max=128),
        ],
    )

    submit = SubmitField("Iniciar sesión")


class ProductForm(FlaskForm):
    name = StringField(
        "Nombre",
        validators=[
            DataRequired(),
            Length(min=3, max=120),
        ],
    )

    description = TextAreaField(
        "Descripción",
        validators=[
            DataRequired(),
            Length(min=10, max=2000),
        ],
    )

    category = StringField(
        "Categoría",
        validators=[
            DataRequired(),
            Length(min=2, max=80),
        ],
    )

    price = DecimalField(
        "Precio",
        places=2,
        validators=[
            DataRequired(),
            NumberRange(
                min=0.01,
                max=999999.99,
            ),
        ],
    )

    stock = IntegerField(
        "Stock",
        validators=[
            DataRequired(),
            NumberRange(
                min=0,
                max=100000,
            ),
        ],
    )

    active = BooleanField(
        "Producto visible",
        default=True,
    )

    image = FileField(
        "Imagen",
        validators=[Optional()],
    )

    submit = SubmitField(
        "Guardar producto"
    )