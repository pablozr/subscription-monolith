async def get_one_user(conn, user_id: int):

    query = "SELECT id, email FROM users WHERE id = $1"

    row = await conn.fetchrow(query, user_id)

    if not row:
        return {"status": False, "message": "User not found", "data": dict()}

    return {
        "status": True,
        "message": "User retrieved successfully",
        "data": {
            "user": {
                "userId": row["id"],
                "email": row["email"]
            }
        }
    }