import os

from cryptography.fernet import Fernet

ENC_KEY = os.environ.get('ENC_KEY', None)
CIPHER_TEXT = os.environ.get('CIPHER_TEXT', None)

if ENC_KEY is None:
    raise KeyError('ENC_KEY is required to decrypt the cipher text')

if CIPHER_TEXT is None:
    raise KeyError('CIPHER_TEXT is required')

f = Fernet(ENC_KEY)
print(f.decrypt(CIPHER_TEXT.encode('utf-8')).decode('utf-8'))
