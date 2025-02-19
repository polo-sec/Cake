from ..number import Number
from cake.abc import FloatType
import typing


class Irrational(Number):
    """
    A class representing an irrational number, subclass of :class:`~cake.core.number.Number`

    If the value is not a float/real it returns a :class:`~cake.core.number.Number`.
    If it is not irrational it returns a :class:`~cake.core.types.real.Real`.
    Else it returns the `Irrational` class.

    You should never feed this class with objects, but the raw value

    Parameters
    ----------
    value: :class:`~cake.abc.FloatType`
        Any object which matches the `FloatType` protocol.
        Defaults to 0
    check_value_attr: :class:`bool`
        See :class:`~cake.Number`
    *args: :class:`~typing.Any`
        See :class:`~cake.Number`
    """

    def __new__(
        cls, value: FloatType = 0, check_value_attr: bool = True, *args, **kwargs
    ):
        from cake import Integer, Real

        is_float = str(value).split(".")
        if len(is_float) == 1:
            return Integer(value)

        if len(is_float[-1]) not in [15, 16]:
            # Not irrational
            return Real(value)

        return super(Irrational, cls).__new__(Irrational)

    def __init__(
        self, value: FloatType = 0, check_value_attr: bool = True, *args, **kwargs
    ):
        super().__init__(
            float(value), check_value_attr, float, Irrational, *args, **kwargs
        )

    @staticmethod
    def handler(res: FloatType):
        return Irrational(real=float(res))

    def __repr__(self) -> str:
        """
        Return the integer set when initialising the class
        """

        return f"Irrational({super().value})"
