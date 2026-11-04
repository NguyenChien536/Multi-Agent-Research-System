"""Encrypted default settings and task snapshot conversion."""
from fastapi import HTTPException
from app.schemas.model_settings import ConnectionUpdate
from app.services.model_connection import ModelConnectionInput, open_connection, seal_connection

def settings_id(user_id):
    return 'settings:' + str(user_id)

def decode_input(stored, owner_id, binding_id):
    connection = open_connection({'_llm_connection': stored}, binding_id, owner_id)
    if connection is None:
        return None
    return ModelConnectionInput(api_key=connection.api_key, **stored['profile'])

def public_profile(stored):
    if not stored:
        return {'connection': None}
    return {'connection': {**stored['profile'], 'has_key': not stored.get('revoked', False)}}

def updated_input(payload, stored, owner_id, binding_id):
    values = payload.model_dump(exclude={'api_key'})
    secret = payload.api_key
    if secret is None:
        try:
            previous = decode_input(stored, owner_id, binding_id)
        except ValueError:
            raise HTTPException(409, 'Enter a new API key to restore this connection') from None
        if previous is None or previous.base_url != payload.base_url.rstrip('/'):
            raise HTTPException(400, 'Enter an API key for the selected service')
        secret = previous.api_key
    try:
        return ModelConnectionInput(api_key=secret, **values)
    except ValueError:
        raise HTTPException(422, 'Invalid API address, model, key or price configuration') from None

def protect(value, binding_id, owner_id):
    try:
        return seal_connection(value, binding_id, owner_id)
    except ValueError:
        raise HTTPException(503, 'Private API connections are not configured securely on this server') from None
