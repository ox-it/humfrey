# From <http://djangosnippets.org/snippets/1095/>.

from django.db import models
from django import forms
from django.conf import settings
import binascii
import random
import string

class EncryptedString(str):
    """A subclass of string so it can be told whether a string is
       encrypted or not (if the object is an instance of this class
       then it must [well, should] be encrypted)."""
    pass


class BaseEncryptedField(models.Field):
    def __init__(self, *args, **kwargs):
        cipher = kwargs.pop('cipher', 'AES')
        imp = __import__('Crypto.Cipher', globals(), locals(), [cipher], -1)
        self.cipher = getattr(imp, cipher).new(settings.SECRET_KEY[:32])
        models.Field.__init__(self, *args, **kwargs)
        
    def to_python(self, value):
        try:
            return self.cipher.decrypt(binascii.a2b_hex(str(value))).split('\0')[0]
        except Exception:
            return value
    
    def get_db_prep_value(self, value):
        if isinstance(value, unicode):
            padding = 2 * self.cipher.block_size - len(value) % self.cipher.block_size
            if True or padding and padding < self.cipher.block_size:
                value += "\0" + ''.join([random.choice(string.printable) for index in range(padding-1)])
            value = EncryptedString(binascii.b2a_hex(self.cipher.encrypt(value)))
        return value

class EncryptedTextField(BaseEncryptedField):
    __metaclass__ = models.SubfieldBase

    def get_internal_type(self): 
        return 'TextField'
    
    def formfield(self, **kwargs):
        defaults = {'widget': forms.PasswordInput}
        defaults.update(kwargs)
        return super(EncryptedTextField, self).formfield(**defaults)

class EncryptedCharField(BaseEncryptedField):
    __metaclass__ = models.SubfieldBase

    def get_internal_type(self):
        return "CharField"
    
    def formfield(self, **kwargs):
        defaults = {'widget': forms.PasswordInput,
                    'max_length': self.max_length}
        defaults.update(kwargs)
        return super(EncryptedCharField, self).formfield(**defaults)