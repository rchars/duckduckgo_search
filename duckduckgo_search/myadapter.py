from functools import wraps
import inspect
import pathlib
import click
import ast

from . import cli
from .mycli import (
    my_images as my_images_impl,
    my_chat as my_chat_impl
)

class HandleDecorators:
    original_cli_path = pathlib.Path(__file__).parent / pathlib.Path('cli.py')
    original_cli_code = original_cli_path.read_text()

    def __init__(self, original_function, custom_function):
        self.original_function = original_function
        self.custom_function = custom_function

    def extract_click_option_decorators(self):
        decorators = []
        if hasattr(self.original_function, 'params'):
            for param in self.original_function.params:
                if isinstance(param, click.Option):
                    decorators.append(param)
        return decorators

    def get_decorator_parameter_names(self, opts):
        tree = ast.parse(self.original_cli_code)
        decorator_params = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == self.original_function.name:
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr == 'option':
                            decorator_opts = [arg.s for arg in decorator.args if isinstance(arg, ast.Str)]
                            if opts == decorator_opts:
                                # Extract parameter names
                                for kwarg in decorator.keywords:
                                    if isinstance(kwarg.value, ast.Constant):
                                        decorator_params.append(kwarg.arg)
                                    elif isinstance(kwarg.value, ast.Str):
                                        decorator_params.append(kwarg.arg)
                                    elif isinstance(kwarg.value, ast.Num):
                                        decorator_params.append(kwarg.arg)
        return decorator_params

    def apply_decorators_to_custom_function(self):
        decorators = self.extract_click_option_decorators()
        @click.command(context_settings=self.original_function.context_settings)
        @wraps(self.custom_function)
        def wrapped_function(*args, **kwargs):
            return self.custom_function(*args, **kwargs)

        for decorator in reversed(decorators):
            opts = decorator.opts
            param_names = self.get_decorator_parameter_names(opts)
            valid_kwargs = {
                param_name: getattr(decorator, param_name)
                for param_name in param_names
                if hasattr(decorator, param_name)
            }
            wrapped_function = click.option(*opts, **valid_kwargs)(wrapped_function)
        return wrapped_function

@click.group()
def cli_group():
    pass

def add_original_commands():
    for attr_name in dir(cli):
        attr = getattr(cli, attr_name)
        if isinstance(attr, click.Command):
            cli_group.add_command(attr, attr_name)

def add_custom_commands():
    images_handler = HandleDecorators(cli.images, my_images_impl)
    custom_images_command = images_handler.apply_decorators_to_custom_function()
    cli_group.add_command(custom_images_command, 'myimages')

    chat_handler = HandleDecorators(cli.chat, my_chat_impl)
    custom_chat_command = chat_handler.apply_decorators_to_custom_function()
    cli_group.add_command(custom_chat_command, 'mychat')

def main():
    add_custom_commands()
    add_original_commands()
    cli_group()

if __name__ == '__main__':
    main()
