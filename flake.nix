{
  description = "WhatsApp-Taskwarrior: an agent-managed Taskwarrior list from WhatsApp group chats";

  inputs = {
    # The whatsapp-mcp submodule (bridge + MCP server) is part of the source.
    self.submodules = true;
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (
        pkgs:
        let
          python = pkgs.python312;
        in
        rec {
          # The wtw CLI. Its tests run against a real (throwaway) Taskwarrior.
          wtw = python.pkgs.buildPythonApplication {
            pname = "whatsapp-taskwarrior";
            version = "0.1.0";
            pyproject = true;
            src = pkgs.lib.fileset.toSource {
              root = ./.;
              fileset = pkgs.lib.fileset.unions [
                ./pyproject.toml
                ./README.md
                ./src
                ./tests
                ./examples
                ./scripts/demo.sh
              ];
            };
            build-system = [ python.pkgs.hatchling ];
            nativeCheckInputs = [
              python.pkgs.pytestCheckHook
              pkgs.taskwarrior3
            ];
            # tests/test_demo.py runs scripts/demo.sh, which needs a shebang that works in the sandbox.
            postPatch = "patchShebangs scripts";
            meta.mainProgram = "wtw";
          };

          # The Go WhatsApp bridge from third_party/whatsapp-mcp.
          whatsapp-bridge = (pkgs.buildGoModule.override { go = pkgs.go_1_26; }) {
            pname = "whatsapp-bridge";
            version = "0-unstable";
            src = ./third_party/whatsapp-mcp/whatsapp-bridge;
            vendorHash = "sha256-y/+6nSUDAs5oc/0BmZuOvwnTWrzkdgvFBuYiktbAjec=";
            env.CGO_ENABLED = 1;
            # Upstream's tests need network and a paired phone.
            doCheck = false;
            postInstall = ''
              mv $out/bin/whatsapp-client $out/bin/whatsapp-bridge
            '';
            meta.mainProgram = "whatsapp-bridge";
          };

          default = wtw;
        }
      );

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            # Python: this project and the upstream MCP server (uv-managed venvs)
            python312
            uv
            # Go: the bridge (go-sqlite3 needs CGO; mkShell provides a C compiler)
            go_1_26
            golangci-lint
            pkg-config
            # Runtime tools
            taskwarrior3
            sqlite
            ffmpeg
            # Dev tools
            just
            shellcheck
            shfmt
            jq
            nixfmt
          ];
          env = {
            CGO_ENABLED = "1";
            # Use the Go and Python from this shell instead of downloading others.
            GOTOOLCHAIN = "local";
            UV_PYTHON = "${pkgs.python312}/bin/python3";
            UV_PYTHON_DOWNLOADS = "never";
          };
        };
      });

      checks = forAllSystems (pkgs: {
        inherit (self.packages.${pkgs.stdenv.hostPlatform.system}) wtw whatsapp-bridge;
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
