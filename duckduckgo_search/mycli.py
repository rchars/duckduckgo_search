from concurrent.futures import ThreadPoolExecutor, as_completed
from mimetypes import guess_type, guess_extension
from collections import namedtuple
from urllib.parse import urlparse
from types import SimpleNamespace
from datetime import datetime

import subprocess
import filecmp
import inspect
import pathlib
import click
import sys

from .duckduckgo_search import DDGS
from .utils import _expand_proxy_tb_alias, json_loads
from .cli import _sanitize_keywords, _download_file, _save_json

ArgumentBundle = namedtuple('ArgumentBundle', ['original_kwargs', 'ddgs_kwargs', 'original_ns', 'ddgs_ns'])

def setup_kwargs(func, *args, **kwargs):
    spec = inspect.getfullargspec(func)
    ddgs_kwargs = {}
    for arg_name in spec.args:
        try:
            val = kwargs[arg_name]
            if val is None: continue
            ddgs_kwargs[arg_name] = val
        except KeyError: pass
    argument_bundle = ArgumentBundle(
        original_kwargs=kwargs,
        ddgs_kwargs=ddgs_kwargs,
        original_ns=SimpleNamespace(**kwargs),
        ddgs_ns=SimpleNamespace(**ddgs_kwargs)
    )
    return argument_bundle

@click.option('--del-duplicates', is_flag=True, default=False)
@click.option('--remove-metadata', is_flag=True, default=False)
@click.option('--folder', required=True, type=click.Path(exists=True, file_okay=False, dir_okay=True))
def my_images(*args, **kwargs):
    argument_bundle = setup_kwargs(DDGS.images, *args, **kwargs)
    original_ns = argument_bundle.original_ns
    data = DDGS(proxy=_expand_proxy_tb_alias(original_ns.proxy)).images(
        **argument_bundle.ddgs_kwargs
    )
    sanitized_keywords = _sanitize_keywords(original_ns.keywords)
    threads = 10 if original_ns.threads is None else original_ns.threads
    path = original_ns.folder
    images_dir = pathlib.Path(path)
    with ThreadPoolExecutor(max_workers=original_ns.threads) as executor:
        futures = []
        for i, res in enumerate(data, start=1):
            url = res['image']
            parsed_url = urlparse(url)
            mime_type, _ = guess_type(parsed_url.path)
            if mime_type: extension = guess_extension(mime_type) or ''
            else: extension = ''
            current_time = datetime.now()
            filename = f"{i}{current_time.tzinfo}{current_time.strftime('%Y%m%d')}{current_time.strftime('%H%M%S')}{current_time.microsecond // 1000:03d}{current_time.second}{current_time.minute}{current_time.hour}{extension}"
            future = executor.submit(_download_file, url, path, filename, original_ns.proxy)
            futures.append(future)
        with click.progressbar(length=len(futures), label="Downloading", show_percent=True, show_pos=True, width=50) as bar:
            for future in as_completed(futures):
                future.result()
                bar.update(1)
    print("Checking if exiftool is installed")
    if original_ns.remove_metadata:
        try:
            subprocess.run(["exiftool"], capture_output=True)
        except FileNotFoundError:
            print("Exiftool is not installed, cannot remove metadata")
        else:
            print("Calling exiftool...")
            for dir_elem in images_dir.iterdir():
                if not dir_elem.is_file(): continue
                if subprocess.call(["exiftool", "-all=", "-overwrite_original", "-ext", "*", str(dir_elem)]) != 0: dir_elem.unlink()
    if original_ns.del_duplicates:
        print("Checking for duplicates...")
        for dir_elem_1 in images_dir.iterdir():
            if not dir_elem_1.is_file(): continue
            for dir_elem_2 in images_dir.iterdir():
                if not dir_elem_2.is_file() or dir_elem_1 == dir_elem_2: continue
                if filecmp.cmp(dir_elem_1, dir_elem_2, shallow=False):
                    dir_elem_2.unlink()
                    print(f"{dir_elem_1} and {dir_elem_2} were the same, removed duplicate")

@click.option('--cache-file', type=click.Path(), default=None)
def my_chat(*args, **kwargs):
    original_ns = SimpleNamespace(**kwargs)
    client = DDGS(proxy=_expand_proxy_tb_alias(original_ns.proxy))
    model = ["gpt-4o-mini", "claude-3-haiku", "llama-3.1-70b", "mixtral-8x7b"][int(original_ns.model) - 1]
    multiline_letter = "Z" if sys.platform == "win32" else "D"
    if original_ns.multiline:
        def input_action():
            print(f"{'-' * 78}\nYou[{model=} tokens={client._chat_tokens_count}]: ", end="")
            print(f"""[multiline, send message: ctrl+{multiline_letter}]""")
            user_input = sys.stdin.read()
            print("...")
            return user_input
    else:
        import readline
        readline.set_auto_history(False)
        readline.clear_history()
        def input_action():
            return input(f"{'-' * 78}\nYou[{model=} tokens={client._chat_tokens_count}]: ")
    if original_ns.cache_file is not None:
        cache_file = pathlib.Path(original_ns.cache_file)
        def save_action(user_input):
            if user_input.strip():
                resp_answer = client.chat(keywords=user_input, model=model, timeout=original_ns.timeout)
                click.secho(f"AI: {resp_answer}", fg="bright_yellow")
                cache = {"vqd": client._chat_vqd, "tokens": client._chat_tokens_count, "messages": client._chat_messages}
                _save_json(cache_file, cache)
        def loop_action():
            while True: save_action(input_action())
        if original_ns.load and cache_file.is_file():
            with cache_file.open() as f:
                cache = json_loads(f.read())
                client._chat_vqd = cache.get("vqd", None)
                client._chat_messages = cache.get("messages", [])
                client._chat_tokens_count = cache.get("tokens", 0)
    else:
        def loop_action():
            while True:
                resp_answer = client.chat(keywords=input_action(), model=model, timeout=original_ns.timeout)
                click.secho(f"AI: {resp_answer}", fg="bright_yellow")
    loop_action()
