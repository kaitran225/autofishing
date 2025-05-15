"""
Dummy key sender implementation for unsupported platforms.
"""

class DummyKeySender:
    def __init__(self):
        print("WARNING: Using dummy key sender implementation")
        print("This platform is not supported for key sending")
        print("Autofisher only fully supports Windows and macOS")
    
    def send_key(self, key):
        """Dummy implementation of send_key"""
        print(f"Dummy: Would send key '{key}' if platform was supported")
        return False
    
    def send_key_combination(self, keys):
        """Dummy implementation of send_key_combination"""
        if isinstance(keys, list):
            keys_str = ' + '.join(keys)
        else:
            keys_str = keys
        print(f"Dummy: Would send key combination '{keys_str}' if platform was supported")
        return False 