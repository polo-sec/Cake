from token import INDENT
from cake.core.markers import ALLOWED
import re
import typing
import string

from cake import abc, errors

from cake import (
    Complex, Integer, Irrational, Prime, Float, Unknown,

    Operator, Symbol, PlusOrMinus, Function
)
from cake.helpers import convert_type

# Imports for tokenizing
from tokenize import (
    tokenize, 
    
    # IGNORE MARKERS
    ENDMARKER, NEWLINE, ENCODING,
    
    # MARKERS TO SEARCH
    OP, NAME, NUMBER, ERRORTOKEN
)
from io import BytesIO

ASCII_CHARS = string.ascii_lowercase
# Use lowercases so `X` is equal to `x`
BLACKLISTED = list(abc.KEYWORDS.keys()) + list(abc.CONSTANTS.keys())
# Keywords that cant be assigned to an unknown
VALID_SYMBOLS = {
    "!", "(", ")"
}
# Used for parsing functions
IGNORE = (ENDMARKER, NEWLINE, ENCODING)
# Ignore any tokens from the tokeniser

################
#
# Regex patterns
#
################

FIND_UNKNOWNS = re.compile(
    "[a-zA-Z]+",
    re.IGNORECASE
)
# Looks for any letters, this is useful when mapping values to a specific unknown

INVALID_OPS = re.compile(
    "[a-zA-Z]+[0-9]+", re.IGNORECASE
)
# Looks for any incorrect patterns such as `sqrt4`

# Main Object

class Equation(object):
    """
    Create simple mathmatical equations and statements and solve by providing values.
    If you supply an equation with multiple lines, it splits them and returns a list of equations instead of a single equation object

    Example
    -------
    
    .. code-block:: py

        >>> from cake import Equation
        >>> circle, line = Equation('(x ** 2) + (y ** 2)\n2x + y')

    Parameters
    ----------
    equation: :class:`str`
        The statement used when processing your statement
    *default_args: :class:`~typing.Any`:
        Default set of arguments used when substituting the equation, IF they are not supplied during substitution.
        If you supply some, it skips the provided ones and uses the ones that havent been provided.

        Example
        -------
        
        .. code-block:: py

            >>> from cake import Equation
            >>> y = Equation("2x + 3", 1)
            >>> y._sub()
            [Symbol('('), Integer(1), ..., Operator(+), Integer(3)]
    **default_kwargs: :class:`~typing.Mapping[str, typing.Any]`
        A set of keyword arguments use when substituting the equation, IF they have not been supplied during substitution.
        Compared to ``default_args``, this allows you to choose which arguments to supply.

        Example
        -------

        .. code-block:: py

            >>> from cake import Equation
            >>> eq = Equation("x ** 2 + y ** 2")
            >>> eq._sub(y=10)
            [Unknown(x), ..., Operator(+), Integer(10), ...]

    
    """
    def __new__(cls, equation: typing.Union[str, list], *default_args, **default_kwargs):
        multiple = equation.split('\n') if type(equation) == str else equation
        if len(multiple) > 1:
            eqs = list()

            for eq in multiple:
                eqs.append(Equation(eq, *default_args, **default_kwargs))
            return eqs

        return super(Equation, cls).__new__(Equation, *default_args, **default_kwargs)

    def __init__(self, equation: typing.Union[str, typing.BinaryIO], *default_args, **default_kwargs) -> None:
        default_args = list(default_args)

        if hasattr(equation, 'seek'):
            self.__equation = equation.read().decode(encoding='ASCII', errors='ignore')
        else:
            self.__equation = equation.lower()

        self.args = default_args
        self.kwargs = default_kwargs

        self.__mappings = self._sort_values(*default_args, **default_kwargs)

    def _sort_values(self, *args, **kwargs) -> dict:
        unknowns = FIND_UNKNOWNS.findall(self.__equation)
        for value in unknowns.copy():
            # Copy stops the change size during iteration error

            if value in BLACKLISTED:
                unknowns.remove(value)


        as_dict = {i: None for i in unknowns}
        keys = list(as_dict.keys())

        if not keys:
            return {}

        current_key = keys[0]
        current_index = 0

        for arg in args:
            if (current_index + 1) > len(keys):
                break

            as_dict[current_key] = arg
            current_index += 1

        for key, value in kwargs.items():
            if key in as_dict:
                as_dict[key] = value

        as_dict = {k: v for k, v in as_dict.items() if v != None}

        return as_dict

    def _sub(self, 
            update_mappings: bool = False,
            return_tokens: bool = False,
            *args, **kwargs
        ):
        """
        Simple tokenization, returns a list of tokens. This is usually only important for parsing.
        An example of this can be found in the ``substitution`` method.

        Parameters
        ----------
        update_mappings: :class:`bool`
            Update the inner unknown mappings with any new args or kwargs
        return_tokens: :class:`bool`
            Returns a tuple with ``(Evaluated_Tokens, Tokens)``
        *args, **kwargs: :class:`~typing.Any`
            Overwrites or adds to pre-existing inner mappings for unknown values
        """

        if update_mappings:
            self.update_variables(*args, **kwargs)
            unknown_mapping = self.__mappings
        else:
            unknown_mapping = self.update_variables(False, *args, **kwargs)

        invalid = INVALID_OPS.findall(self.equation)
        if invalid:
            found_first = invalid[0]
            index = 0

            while True:
                if index == len(found_first):
                    break

                if found_first[index].isdigit():
                    break
                index += 1

            possible_correct = found_first[:index]
            possible_correct += ' '
            possible_correct += found_first[index:]

            raise errors.EquationParseError(f'String `{found_first}`, followed by integer. Perhaps you ment "{possible_correct}"')

        as_file = BytesIO(self.equation.encode(encoding='ASCII', errors='ignore'))

        as_file.seek(0)

        tokens = list(tokenize(as_file.readline))

        presence = list()

        OPEN_BRACKETS = 0
        ACTUAL_INDEX = 0
        TOKEN_INDEX = 0

        SKIP = 0

        while True:
            if TOKEN_INDEX > (len(tokens) - 1):
                break

            if SKIP:
                SKIP -= 1
                TOKEN_INDEX += 1
                continue

            token = tokens[TOKEN_INDEX]

            string = (token.string).lower()
            type_ = token.type

            if type_ in IGNORE:
                pass

            elif type_ == OP:
                if string == '(':
                    POS_TOKENS = tokens[TOKEN_INDEX:]

                    is_plus = POS_TOKENS[0:5]
                    to_mapping = ''.join([i.string for i in is_plus])

                    if to_mapping in ['(+|-)', '(-|+)']:
                        SKIP += 4
                        presence.append(PlusOrMinus())
                    else:
                        try:
                            comp = Complex(raw=to_mapping)
                            presence.append(comp)

                            SKIP += 4
                        except ValueError:
                            presence.append(Symbol('('))
                            OPEN_BRACKETS += 1

                elif string == ')':
                    if OPEN_BRACKETS < 1:
                        INCORRECT_BRACK_INDEX = token.start[1]

                        raise errors.EquationParseError(f'Unexpected `)` at position {INCORRECT_BRACK_INDEX}')

                    presence.append(Symbol(')'))
                    OPEN_BRACKETS -= 1

                else:
                    string_ = abc.MAP_OPERATORS.get(string, string)
                    # Get the operator or just return the same string

                    try:
                        op = Operator(string_)
                        presence.append(op)
                    except ValueError as e:
                        raise errors.EquationParseError(
                            f'Unknown Operator: {string}'
                        ) from e

            elif type_ in [NAME, ERRORTOKEN]:
                constant = abc.CONSTANTS.get(string)
                function = abc.KEYWORDS.get(string)
                symbol_func = abc.SYMBOL_KW.get(string)

                if constant and function:
                    raise errors.EquationParseError(f'{string} is defined both as a function and constant')

                elif constant:
                    presence.append(Irrational(constant))
                
                elif function:
                    POS_TOKENS = tokens[(TOKEN_INDEX + 1):]
                    # Start from next posfix, else the `function` NAME gets caught

                    if not POS_TOKENS:
                        raise errors.EquationParseError(f'{string} Called with no parameters')

                    if POS_TOKENS[0].string == '(':
                        WRAPPED_IN_BRACKETS = True
                    else:
                        WRAPPED_IN_BRACKETS = False

                    if not WRAPPED_IN_BRACKETS:
                        _, COL = POS_TOKENS[0].start

                        EQ = self.equation[COL:]
                        EVALUATE = EQ.split(' ')[0]

                        TREE, TOKENS = Equation(EVALUATE)._sub(
                            return_tokens=True,
                            **self._sort_values(*args, **kwargs)
                            )
                        
                    else:
                        FUNQ_EQ = ""
                        BRACKS = 0

                        for POSFIX in POS_TOKENS:

                            if POSFIX.string == '(':
                                BRACKS += 1
                                FUNQ_EQ += ' ( '
                            elif POSFIX.string == ')':
                                if BRACKS < 1:
                                    OPEN_BRACKETS -= 1
                                    presence.append(Symbol(')'))
                                    break
                                BRACKS -= 1
                                FUNQ_EQ += ' ) '

                            else:
                                FUNQ_EQ += f' {POSFIX.string} '

                        if BRACKS > 1:
                            raise errors.EquationParseError(f'{BRACKS} Unclosed brackets whilst evaluating {function.__qualname__}')
                        
                        TREE, TOKENS = Equation(FUNQ_EQ)._sub(
                            return_tokens=True, 
                            **self._sort_values(*args, **kwargs)
                            )

                    if not TREE:
                        raise errors.EquationParseError(f'{string} Called with no parameters')

                    func = Function(function, TREE)
                    SKIP += len(TOKENS)
                    presence.append(func)

                elif symbol_func:
                    LAST_POSFIX = presence[-1]
                    func_name = symbol_func.__qualname__.title()

                    if isinstance(LAST_POSFIX, Operator):
                        raise errors.EquationParseError(f'{func_name} called on an operator ({LAST_POSFIX.value}), at index {token.start[1]}.')                    

                    if isinstance(LAST_POSFIX, Symbol):
                        if LAST_POSFIX.value == '(':
                            raise errors.EquationParseError(f'{func_name} called on an open bracket, at index {token.start[1]}')
                        
                        OPEN_BRACKS = 0

                        raise NotImplementedError('Factorial on bracket groups is not yet implemented')

                    else:
                        new_pre = [
                            Symbol('('),
                            LAST_POSFIX,
                            Symbol(')')
                        ]

                        func = Function(
                            symbol_func, new_pre
                        )

                        presence[-1] = func

                else:
                    unk = Unknown(string)
                    value = unknown_mapping.get(string)

                    if value:
                        presence.append(convert_type(value))
                    else:
                        presence.append(unk)

            elif type_ == NUMBER:
                POS_TOKENS = tokens[TOKEN_INDEX:]
                CURRENT_NUMBER = convert_type(string)

                if not POS_TOKENS:
                    presence.append(CURRENT_NUMBER)
                else:
                    NEXT = POS_TOKENS[1]

                    if NEXT.type == NAME:
                        constant = abc.CONSTANTS.get(NEXT.string)
                        function = abc.KEYWORDS.get(NEXT.string)

                        value = unknown_mapping.get(NEXT.string)
                        unk = Unknown(NEXT.string)

                        if value:
                            value = convert_type(value)
                        else:
                            value = unk

                        if constant:
                            SKIP += 1
                            presence.append(Irrational(constant))

                        elif not function:
                            SKIP += 1

                            presence.extend([
                                Symbol('('),
                                CURRENT_NUMBER,
                                Operator('*'),
                                value,
                                Symbol(')')
                            ])

                        else:
                            possible_correct = f'{string} * {NEXT.string}'

                            raise errors.EquationParseError(
                                f'Invalid use of function "{function.__qualname__}" at index {NEXT.start[1]}. Perhaps you ment "{possible_correct}"'
                            )


                    else:
                        presence.append(CURRENT_NUMBER)

            else:

                # Stops `' '` from raising an error
                if string.strip(): 
                    raise errors.EquationParseError(f'Unknown Token: {string}')

            ACTUAL_INDEX += len(string)
            TOKEN_INDEX += 1

        if OPEN_BRACKETS > 1:
            raise errors.EquationParseError(f'{OPEN_BRACKETS} Unclosed brackets')

        if return_tokens:
            return presence, tokens
        return presence

    def substitute(self, *args, **kwargs):
        """
        Supply values, or use pre-existing values to substitute into your equation.
        Returns the result of the evaluated equation.

        Parameters
        ----------
        *args: :class:`~typing.Any`
            Arguments to supply in your equation
        **kwargs: :class:`~typing.Any`
            Keyworded arguments to supply into your equation.
        """
        raise NotImplementedError()

    def solve(self, *args, **kwargs):
        """
        Equals your equation to ``0`` and solves it mathmatically.

        Parameters
        ----------
        *args: :class:`~typing.Any`
            Arguments to supply in your equation
        **kwargs: :class:`~typing.Any`
            Keyworded arguments to supply into your equation.

            **Warning:** Unlike `*args`, this will overwrite all instances of an unknown
        """
        raise NotImplementedError()

    def wrap_all(self, operator: str, ending: str, *eq_args, **eq_kwargs) -> None:
        """
        Places the entire of your current equation into brackets and adds and operator with another query.

        Example
        ^^^^^^^
        .. code-block:: py

            >>> from cake import Equation
            >>> y = Equation("2x + 2")
            >>> y.wrap_all("*", "2")
            >>> y
            (2x + 2) * 2

        Parameters
        ----------
        operator: :class:`str`
            The operator to use with the ending, check out how the ``Operator`` class works for more details.
        ending: :class:`str`
            A seperate query to append onto the end
        *args: :class:`~typing.Any`
            Arguments for any new vars, its best to do ``list(Equation.args) + [...]``
        **kwargs: :class:`~typing.Any`
            Keyworded arguments, works the same way as `*args`, except is much easier to implement.
        """
        op = Operator(operator)

        eq = f'({self.__equation})'
        eq += f' {op.value} {ending}'

        self.__equation = eq

        self.update_variables(*eq_args, **eq_kwargs)

    def update_variables(self, overwrite: bool = True, *args, **kwargs) -> typing.Union[dict, None]:
        """
        Update the built in mapping for unknown values

        Paramters
        ---------
        overwrite: :class:`bool`
            Should overwrite the current mapping, or return the mapping which was just created.

            Defaults to ``True``.
        *args: :class:`~typing.Any`
            Arguments to replace, it works by adding new arguments to the start and trimming down the current args.

            So if you had ``10, 20`` as your arguments and you supply ``30`` it becomes ``30, 20``.
        **kwargs: :class:`~typing.Any`
            Keyworded arguments to change or add to your equation unknown mapping
        """

        current_args = self.args
        default_args = list(args) + current_args[len(args):]

        default_kwargs = {**self.kwargs, **kwargs}

        mapping = self._sort_values(*default_args, **default_kwargs)

        if overwrite:
            self.args = default_args
            self.kwargs = default_kwargs

            self.__mappings = mapping
        else:
            return mapping

    @property
    def mapping(self):
        """ Returns a copy of the variable mappings for unknowns """
        return self.__mappings.copy()

    @property
    def equation(self):
        """ Returns a copy of the equation used when initialsing the class """
        return self.__equation

    def __repr__(self) -> str:
        """
        Returns the equation set when initialising the class
        """

        return repr(self.equation)
