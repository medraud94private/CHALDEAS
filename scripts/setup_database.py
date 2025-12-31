"""
CHALDEAS 데이터베이스 설정 스크립트

PostgreSQL에 chaldeas 데이터베이스와 사용자를 생성하고
pgvector 확장을 활성화합니다.
"""

import os
import sys
import subprocess
from pathlib import Path

# PostgreSQL 설정
PG_HOST = "localhost"
PG_PORT = "5432"
PG_ADMIN_USER = "postgres"
PG_ADMIN_PASSWORD = "ch001510"  # postgres 관리자 비밀번호

# CHALDEAS 데이터베이스 설정
DB_NAME = "chaldeas"
DB_USER = "chaldeas"
DB_PASSWORD = "chaldeas_dev"

# PostgreSQL bin 경로
PSQL_PATH = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"


def run_psql(sql: str, database: str = "postgres", admin: bool = True):
    """psql 명령 실행"""
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_ADMIN_PASSWORD if admin else DB_PASSWORD

    user = PG_ADMIN_USER if admin else DB_USER

    cmd = [
        PSQL_PATH,
        "-h", PG_HOST,
        "-p", PG_PORT,
        "-U", user,
        "-d", database,
        "-c", sql
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


def main():
    print("=" * 50)
    print("CHALDEAS 데이터베이스 설정")
    print("=" * 50)

    # 1. 연결 테스트
    print("\n1. PostgreSQL 연결 테스트...")
    result = run_psql("SELECT version();")
    if result.returncode != 0:
        print(f"연결 실패: {result.stderr}")
        print("postgres 비밀번호를 확인하세요.")
        sys.exit(1)
    print("   연결 성공!")

    # 2. 사용자 생성
    print(f"\n2. 사용자 '{DB_USER}' 생성...")
    result = run_psql(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{DB_USER}') THEN
                CREATE USER {DB_USER} WITH PASSWORD '{DB_PASSWORD}';
                RAISE NOTICE 'User created';
            ELSE
                RAISE NOTICE 'User already exists';
            END IF;
        END
        $$;
    """)
    if result.returncode == 0:
        print("   완료!")
    else:
        print(f"   경고: {result.stderr}")

    # 3. 데이터베이스 생성
    print(f"\n3. 데이터베이스 '{DB_NAME}' 생성...")

    # 먼저 존재 확인
    result = run_psql(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}';")

    if "1" not in result.stdout:
        result = run_psql(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};")
        if result.returncode == 0:
            print("   생성 완료!")
        else:
            print(f"   오류: {result.stderr}")
    else:
        print("   이미 존재함")

    # 4. 권한 부여
    print(f"\n4. 권한 부여...")
    run_psql(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};")
    run_psql(f"GRANT ALL ON SCHEMA public TO {DB_USER};", database=DB_NAME)
    print("   완료!")

    # 5. pgvector 확장 생성
    print(f"\n5. pgvector 확장 활성화...")
    result = run_psql("CREATE EXTENSION IF NOT EXISTS vector;", database=DB_NAME)
    if result.returncode == 0:
        print("   완료!")
    else:
        print(f"   오류: {result.stderr}")

    # 6. 확인
    print(f"\n6. 설정 확인...")
    result = run_psql("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';", database=DB_NAME)
    print(result.stdout)

    # 7. .env 파일 업데이트
    print("\n7. .env 파일 확인...")
    env_path = Path(__file__).parent.parent / ".env"
    db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{PG_HOST}:{PG_PORT}/{DB_NAME}"

    if env_path.exists():
        content = env_path.read_text()
        if "DATABASE_URL" in content:
            print(f"   DATABASE_URL이 이미 설정됨")
        else:
            with open(env_path, "a") as f:
                f.write(f"\nDATABASE_URL={db_url}\n")
            print(f"   DATABASE_URL 추가됨")

    print("\n" + "=" * 50)
    print("설정 완료!")
    print("=" * 50)
    print(f"\n연결 문자열:")
    print(f"  {db_url}")


if __name__ == "__main__":
    main()
