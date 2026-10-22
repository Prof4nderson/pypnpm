import os
import sys
import hashlib
import json
import venv
import subprocess
from pathlib import Path

# Repositório Central imutável (Content-Addressable Storage - CAS)
HOME_DIR = Path.home()
PYPNPM_STORE = HOME_DIR / ".pypnpm" / "store" / "v1"

def init_pypnpm_store():
    """Garante a existência da estrutura do repositório central."""
    PYPNPM_STORE.mkdir(parents=True, exist_ok=True)
    print(f"📦 Repositório Central PyPNPM: {PYPNPM_STORE}")

def ensure_venv_exists(project_dir: Path) -> Path:
    """Detecta se o ambiente virtual (.venv) existe no projeto ou cria um do zero."""
    venv_dir = project_dir / ".venv"
    if not venv_dir.exists():
        print(f"⚙️ Ambientes virtuais (.venv) não encontrado em '{project_dir.name}'. Criando novo .venv...")
        venv.create(venv_dir, with_pip=True)
        print(f"✅ .venv criado com sucesso!")
    else:
        print(f"⚡ .venv detectado em: {venv_dir}")
    return venv_dir

def calculate_directory_hash(dir_path: Path) -> str:
    """Gera um hash SHA256 determinístico baseado no conteúdo de todos os arquivos de um pacote."""
    sha256 = hashlib.sha256()
    for file_path in sorted(dir_path.rglob("*")):
        if file_path.is_file():
            sha256.update(file_path.name.encode('utf-8'))
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
    return sha256.hexdigest()

def link_package_to_venv(package_name: str, target_venv_path: Path):
    """Vincular pacote do Store Central para o site-packages do .venv do projeto."""
    source_package_dir = PYPNPM_STORE / package_name

    # Garante que um pacote de demonstração/teste exista no Store caso não tenha sido baixado
    if not source_package_dir.exists():
        source_package_dir.mkdir(parents=True, exist_ok=True)
        (source_package_dir / "__init__.py").write_text(f"# Dummy package for {package_name}\n__version__ = '1.0.0'\n")
        print(f"🛠️ Pacote de teste '{package_name}' gerado no Store Central.")

    # Calcula hash real
    pkg_hash = calculate_directory_hash(source_package_dir)

    site_packages_dir = target_venv_path / "Lib" / "site-packages" / package_name

    if site_packages_dir.exists():
        print(f"ℹ️ Pacote '{package_name}' já vinculado ao .venv.")
        return

    site_packages_dir.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        import _winapi
        try:
            _winapi.CreateJunction(str(source_package_dir), str(site_packages_dir))
            print(f"🔗 [Junction Win32] '{package_name}' linked -> [SHA256: {pkg_hash[:12]}...]")
        except Exception as e:
            print(f"⚠️ Erro ao criar Junction para '{package_name}': {e}")
    else:
        os.symlink(source_package_dir, site_packages_dir)
        print(f"🔗 [Symlink POSIX] '{package_name}' linked -> [SHA256: {pkg_hash[:12]}...]")

def sync_project_dependencies(project_dir: Path):
    """Executa a resolução do projeto baseado no manifesto requirements.pypnpm."""
    req_file = project_dir / "requirements.pypnpm"
    
    if not req_file.exists():
        print(f"❌ Manifesto 'requirements.pypnpm' não encontrado na pasta '{project_dir}'.")
        print("💡 Crie o arquivo ou navegue até a pasta do seu projeto.")
        return

    with open(req_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    project_name = data.get("project", project_dir.name)
    print(f"\n🚀 Sincronizando dependências para o projeto: [{project_name}]")

    # 1. Garante a existência do .venv local
    venv_path = ensure_venv_exists(project_dir)

    # 2. Vincula cada dependência listada
    dependencies = data.get("dependencies", {})
    for pkg_name, pkg_info in dependencies.items():
        print(f"📦 Processando '{pkg_name}' v{pkg_info.get('version', 'latest')}...")
        link_package_to_venv(pkg_name, venv_path)

if __name__ == "__main__":
    print("==============================================")
    print(" 🚀 PyPNPM - CORE ENGINE AGENT (v0.1.0) ")
    print("==============================================")
    init_pypnpm_store()

    # Tenta localizar o manifesto na pasta atual do terminal ou na pasta do próprio script
    current_workspace = Path.cwd()
    if not (current_workspace / "requirements.pypnpm").exists():
        current_workspace = Path(__file__).parent

    sync_project_dependencies(current_workspace)