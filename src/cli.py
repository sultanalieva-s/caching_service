"""``cache-cli``: a small client to exercise the caching service."""

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

import httpx
from pydantic import AliasChoices, AnyHttpUrl, Field, PositiveInt, ValidationError, model_validator
from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, SettingsConfigDict

from src.schemas.payload_schemas import CreatePayloadRequest

STDIO = "-"


class CliSettings(BaseSettings):
    """Command line arguments, parsed and validated by Pydantic Settings."""

    model_config = SettingsConfigDict(cli_prog_name="cache-cli", cli_hide_none_type=True)

    host: AnyHttpUrl = Field(
        AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("h", "host"),
        description="URL of the caching service",
    )
    repeat: PositiveInt = Field(
        1,
        validation_alias=AliasChoices("r", "repeat"),
        description="number of iterations",
    )
    input: str | None = Field(
        None,
        validation_alias=AliasChoices("i", "input"),
        description='input file with the JSON request ("-" for stdin)',
    )
    json_: str | None = Field(
        None,
        validation_alias=AliasChoices("j", "json"),
        description="JSON request passed inline (properly escaped)",
    )
    output: str = Field(
        STDIO,
        validation_alias=AliasChoices("o", "output"),
        description='output file ("-" for stdout)',
    )

    @model_validator(mode="after")
    def input_sources_are_exclusive(self) -> "CliSettings":
        if self.input is not None and self.json_ is not None:
            raise ValueError("--input and --json are mutually exclusive")
        return self

    def read_request(self) -> CreatePayloadRequest:
        """Load and validate the request body from whichever source was given."""
        if self.json_ is not None:
            raw = self.json_
        elif self.input is None or self.input == STDIO:
            raw = sys.stdin.read()
        else:
            raw = Path(self.input).read_text()
        return CreatePayloadRequest.model_validate_json(raw)


def build_parser() -> argparse.ArgumentParser:
    # The task assigns -h to --host, so argparse's default -h/--help must go;
    # --help is re-added on its own.
    parser = argparse.ArgumentParser(prog="cache-cli", add_help=False)
    parser.add_argument("--help", action="help", help="show this help message and exit")
    return parser


@contextmanager
def open_output(target: str) -> Iterator[IO[str]]:
    if target == STDIO:
        yield sys.stdout
    else:
        with open(target, "w") as file:
            yield file


def run(settings: CliSettings) -> None:
    request = settings.read_request()
    base_url = str(settings.host).rstrip("/")

    with httpx.Client(base_url=base_url, timeout=10) as client, open_output(settings.output) as out:
        for _ in range(settings.repeat):
            created = client.post("/payload", json=request.model_dump())
            created.raise_for_status()
            payload_id = created.json()["id"]

            fetched = client.get(f"/payload/{payload_id}")
            fetched.raise_for_status()

            # One JSON object per line keeps repeated runs easy to diff and pipe.
            record = {"id": payload_id, "output": fetched.json()["output"]}
            out.write(json.dumps(record) + "\n")


def main(argv: list[str] | None = None) -> int:
    source = CliSettingsSource(CliSettings, root_parser=build_parser())
    try:
        settings = CliApp.run(CliSettings, cli_args=argv, cli_settings_source=source, cli_exit_on_error=False)
        run(settings)
    except (ValidationError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())