from functools import wraps

import inspect
import click
import copy

from . import cli
from .mycli import (
    my_images as my_images_impl,
    my_chat as my_chat_impl
)

def extract_click_option_decorators(command):
    decorators = []
    if hasattr(command, 'params'):
        for param in command.params:
            if isinstance(param, click.Option):
                decorators.append(param)
    return decorators

def apply_decorators_to_custom_function(original_command, custom_function):
    decorators = extract_click_option_decorators(original_command)
    @click.command(context_settings=original_command.context_settings)
    @wraps(custom_function)
    def wrapped_function(*args, **kwargs): return custom_function(*args, **kwargs)
    decorator_signature = inspect.signature(click.Option.__init__)
    for decorator in reversed(decorators):
        decorator_copy = copy.deepcopy(decorator)
        opts = decorator_copy.opts
        valid_kwargs = {
            param_name: getattr(decorator_copy, param_name)
            for param_name in decorator_signature.parameters
            if hasattr(decorator_copy, param_name)
        }
        valid_kwargs['default'] = decorator.default
        valid_kwargs['required'] = decorator.required
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
    custom_images_command = apply_decorators_to_custom_function(cli.images, my_images_impl)
    cli_group.add_command(custom_images_command, 'myimages')
    custom_chat_command = apply_decorators_to_custom_function(cli.chat, my_chat_impl)
    cli_group.add_command(custom_chat_command, 'mychat')

def main():
    add_custom_commands()
    add_original_commands()
    cli_group()

if __name__ == '__main__':
    main()
