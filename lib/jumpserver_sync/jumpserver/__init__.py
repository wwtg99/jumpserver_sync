from jumpserver_sync.utils import JumpserverError
from jumpserver_sync.jumpserver.clients import AdminUser, Domain, Label, Node, Asset


class LabelTag:
    """
    Present for asset label.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value

    @classmethod
    def create_tag(cls, obj):
        if 'key' in obj:
            key = obj['key']
        elif 'Key' in obj:
            key = obj['Key']
        elif 'name' in obj:
            key = obj['name']
        else:
            raise JumpserverError('Could not transform object {} to LabelTag.'.format(obj))
        if 'value' in obj:
            value = obj['value']
        elif 'Value' in obj:
            value = obj['Value']
        else:
            raise JumpserverError('Could not transform object {} to LabelTag'.format(obj))
        return LabelTag(key=key, value=value)

    def __eq__(self, other):
        if isinstance(other, LabelTag):
            return self.key == other.key and self.value == other.value
        return False

    def __str__(self):
        return '{}:{}'.format(self.key, self.value)
