from marshmallow import Schema, fields


class AdminSchema(Schema):
    id = fields.Int(required=False)
    email = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)


class UserSchema(Schema):
    id = fields.Int(required=False)
    user_id = fields.Int(required=True)
    first_name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    win_count = fields.Int(required=True)


class UserListSchema(Schema):
    users = fields.Nested(UserSchema, many=True)
