"""
pgvector 자동 설치 스크립트 (Windows PostgreSQL)

사용법:
    python scripts/install_pgvector.py

요구사항:
    - 관리자 권한으로 실행
    - PostgreSQL 18 설치됨
"""

import os
import sys
import zipfile
import shutil
import subprocess
import urllib.request
import tempfile
from pathlib import Path


# 설정
PGVECTOR_VERSION = "0.8.1"
PG_VERSION = "18"
RELEASE_TAG = f"{PGVECTOR_VERSION}_{PG_VERSION}.0.2"
DOWNLOAD_URL = f"https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/{RELEASE_TAG}/vector.v{PGVECTOR_VERSION}-pg{PG_VERSION}.zip"

# PostgreSQL 경로 (자동 감지)
PG_PATHS = [
    f"C:\\Program Files\\PostgreSQL\\{PG_VERSION}",
    f"C:\\PostgreSQL\\{PG_VERSION}",
    f"/usr/lib/postgresql/{PG_VERSION}",  # Linux
]


def find_pg_path():
    """PostgreSQL 설치 경로 찾기"""
    for path in PG_PATHS:
        if os.path.exists(path):
            return Path(path)

    # 환경변수에서 찾기
    pg_home = os.environ.get("PGROOT") or os.environ.get("PG_HOME")
    if pg_home and os.path.exists(pg_home):
        return Path(pg_home)

    return None


def download_pgvector(dest_dir: Path) -> Path:
    """pgvector 바이너리 다운로드"""
    zip_path = dest_dir / f"pgvector-{PGVECTOR_VERSION}.zip"

    print(f"다운로드 중: {DOWNLOAD_URL}")

    try:
        urllib.request.urlretrieve(DOWNLOAD_URL, zip_path)
        print(f"다운로드 완료: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"다운로드 실패: {e}")
        print("\n수동 다운로드 필요:")
        print(f"  https://github.com/andreiramani/pgvector_pgsql_windows/releases/tag/{RELEASE_TAG}")
        sys.exit(1)


def extract_and_install(zip_path: Path, pg_path: Path):
    """압축 해제 및 설치"""
    extract_dir = zip_path.parent / "pgvector_extracted"

    print(f"압축 해제 중: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)

    # 파일 찾기 및 복사
    lib_dir = pg_path / "lib"
    ext_dir = pg_path / "share" / "extension"

    files_copied = 0

    for root, dirs, files in os.walk(extract_dir):
        for file in files:
            src = Path(root) / file

            if file == "vector.dll" or file == "vector.so":
                dst = lib_dir / file
                print(f"복사: {file} -> {dst}")
                shutil.copy2(src, dst)
                files_copied += 1

            elif file.endswith(".control") or file.endswith(".sql"):
                dst = ext_dir / file
                print(f"복사: {file} -> {dst}")
                shutil.copy2(src, dst)
                files_copied += 1

    # 정리
    shutil.rmtree(extract_dir)
    os.remove(zip_path)

    print(f"\n{files_copied}개 파일 설치 완료")
    return files_copied > 0


def check_existing_installation(pg_path: Path) -> bool:
    """기존 설치 확인"""
    dll_path = pg_path / "lib" / "vector.dll"
    control_path = pg_path / "share" / "extension" / "vector.control"

    if dll_path.exists() and control_path.exists():
        print("pgvector가 이미 설치되어 있습니다.")
        return True
    return False


def create_extension(pg_path: Path, database: str = "chaldeas"):
    """PostgreSQL에서 확장 생성"""
    psql = pg_path / "bin" / "psql.exe"
    if not psql.exists():
        psql = pg_path / "bin" / "psql"

    if not psql.exists():
        print("psql을 찾을 수 없습니다. 수동으로 확장을 생성하세요:")
        print(f"  CREATE EXTENSION IF NOT EXISTS vector;")
        return

    # 먼저 데이터베이스 존재 확인 및 생성
    print(f"\n데이터베이스 '{database}' 설정 중...")

    commands = [
        # 데이터베이스 생성 (없으면)
        f'SELECT 1 FROM pg_database WHERE datname = \'{database}\'',
    ]

    try:
        # 데이터베이스 생성
        result = subprocess.run(
            [str(psql), "-U", "postgres", "-tc",
             f"SELECT 1 FROM pg_database WHERE datname = '{database}'"],
            capture_output=True, text=True
        )

        if "1" not in result.stdout:
            print(f"데이터베이스 '{database}' 생성 중...")
            subprocess.run(
                [str(psql), "-U", "postgres", "-c",
                 f"CREATE DATABASE {database}"],
                check=True
            )

        # 확장 생성
        print("pgvector 확장 생성 중...")
        subprocess.run(
            [str(psql), "-U", "postgres", "-d", database, "-c",
             "CREATE EXTENSION IF NOT EXISTS vector"],
            check=True
        )

        # 확인
        result = subprocess.run(
            [str(psql), "-U", "postgres", "-d", database, "-c",
             "SELECT extversion FROM pg_extension WHERE extname = 'vector'"],
            capture_output=True, text=True
        )

        if "0.8" in result.stdout or "0.7" in result.stdout:
            print(f"✓ pgvector 확장 활성화 완료!")
        else:
            print("확장 생성 결과:", result.stdout)

    except subprocess.CalledProcessError as e:
        print(f"확장 생성 실패: {e}")
        print("수동으로 실행하세요:")
        print(f"  psql -U postgres -d {database} -c 'CREATE EXTENSION vector;'")


def main():
    print("=" * 50)
    print("pgvector 자동 설치 스크립트")
    print("=" * 50)

    # PostgreSQL 경로 찾기
    pg_path = find_pg_path()
    if not pg_path:
        print("PostgreSQL 설치를 찾을 수 없습니다.")
        print(f"검색된 경로: {PG_PATHS}")
        sys.exit(1)

    print(f"PostgreSQL 경로: {pg_path}")

    # 기존 설치 확인
    if check_existing_installation(pg_path):
        response = input("다시 설치하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            create_extension(pg_path)
            return

    # 다운로드 및 설치
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_path = download_pgvector(tmp_path)

        if not extract_and_install(zip_path, pg_path):
            print("설치 실패")
            sys.exit(1)

    # 확장 생성
    create_extension(pg_path)

    print("\n" + "=" * 50)
    print("설치 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()
