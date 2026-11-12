# Uses the same nixpkgs source as this pi.dev system's pinned development shell.
{ pkgs ? import /nix/store/2h2cj4clssz0b5s69ifq3whkaxksmj0p-source {} }:
pkgs.mkShell {
  packages = [ pkgs.calibre pkgs.python3Packages.pymupdf ];
  shellHook = ''
    export CALIBRE_PYTHON_PATH="${toString ./src}"
    export PYTHONPATH="${pkgs.calibre}/lib/calibre:$PYTHONPATH"
    export CALIBRE_CONFIG_DIRECTORY="$HOME/.cache/calibre-diagram-dev"
    calibre-debug -c 'from calibre.build_forms import build_forms; build_forms("${toString ./src}", check_icons=False, summary=True)'
  '';
}
