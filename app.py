import os
import random
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from string import ascii_uppercase
from config import login_required

app = Flask(__name__)

secret_key = os.urandom(24).hex()
app.config['SECRET_KEY'] = secret_key
app.config["TEMPLATES_AUTO_RELOAD"] = True
socketio = SocketIO(app)

db = SQL("sqlite:///site.db")

rooms = {}


def generar_code_unico(length):
    while True:
        code = ''.join(random.choices(ascii_uppercase, k=length))
        if code not in rooms:
            break
    return code


@app.route("/")
def direc():
    return render_template("direc.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        usuario = request.form.get("username")
        contraseña = request.form.get("password")

        if not usuario:
            flash("Se espera el nombre del usuario")
            return redirect(url_for("login"))
        elif not contraseña:
            flash("Se espera la contraseña")
            return redirect(url_for("login"))

        rows = db.execute("SELECT * FROM user WHERE usuario = ?", usuario)

        if len(rows) != 1 or not check_password_hash(rows[0]["contraseña"], contraseña):
            flash("Usuario o contraseña incorrecta")
            return redirect(url_for("login"))

        session["user_id"] = rows[0]["id"]
        print(f"Usuario {usuario} ha iniciado sesión con éxito")

        return redirect(url_for("home"))

    else:
        return render_template("login.html", register_link=url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        nombreUsuario = request.form.get("username")
        email = request.form.get("email")
        contraseña = request.form.get("password")
        confirmarContraseña = request.form.get("confirmation")

        if not nombreUsuario:
            flash("Se espera el nombre de usuario")
            return redirect(url_for("register"))
        elif not email:
            flash("Se espera el email")
            return redirect(url_for("register"))
        elif not contraseña:
            flash("Se espera la contraseña")
            return redirect(url_for("register"))
        elif contraseña != confirmarContraseña:
            flash("Las contraseñas no coinciden")
            return redirect(url_for("register"))

        registro = db.execute(
            "SELECT usuario FROM user WHERE usuario = ?", nombreUsuario)
        if registro:
            flash("El nombre de usuario ya existe")
            return redirect(url_for("register"))

        db.execute("INSERT INTO user (email, usuario, contraseña) VALUES (?, ?, ?)",
                   email, nombreUsuario, generate_password_hash(contraseña))

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/home", methods=["POST", "GET"])
@login_required
def home():
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)

        room = code
        if create:
            room = generar_code_unico(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")


@app.route("/room")
@login_required
def room():
    room = session.get("room")
    if not room or not session.get("name") or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])


@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")


@socketio.on("disconnect") 
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")


if __name__ == "__main__":
    socketio.run(app, debug=True)
