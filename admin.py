from app import db, pwd_context

username = "admin"
password = "ChangeMe123!"

with db() as c:
    user = c.execute(
        "SELECT id FROM users WHERE role='super_admin' LIMIT 1"
    ).fetchone()

    password_hash = pwd_context.hash(password)

    if user:
        c.execute(
            "UPDATE users SET username=?, password_hash=?, active=1 WHERE id=?",
            (username, password_hash, user["id"])
        )
    else:
        c.execute(
            """INSERT INTO users
            (username, full_name, password_hash, role)
            VALUES (?, ?, ?, ?)""",
            (username, "System Administrator",
             password_hash, "super_admin")
        )

print("Admin credentials reset successfully!")