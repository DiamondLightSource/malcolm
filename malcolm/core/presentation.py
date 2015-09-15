import abc

from .base import Base


class Presenter(Base):
    @abc.abstractmethod
    def serialize(self, o):
        """Serialize the object to a string"""

    @abc.abstractmethod
    def deserialize(self, s):
        """Serialize the string to an object"""
