import argparse
import getpass
import secrets
from pathlib import Path
from sqlalchemy import select
from .auth import hash_password
from .db import Session
from .models import User, Result, ResultVersion
from .evaluator import MockAdapter
from .worker import search_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['create-admin', 'seed'])
    parser.add_argument('--username', default='admin')
    parser.add_argument('--generate-password', action='store_true', help='Generate a local password and save it to ignored .local-access.md')
    args = parser.parse_args()
    with Session() as db:
        if args.command == 'create-admin':
            if db.scalar(select(User).where(User.username == args.username)):
                raise SystemExit('账号已存在；未修改现有账户')
            password = secrets.token_urlsafe(18) if args.generate_password else getpass.getpass('管理员密码（至少10位）: ')
            if len(password) < 10:
                raise SystemExit('密码至少10位')
            db.add(User(username=args.username, password_hash=hash_password(password), role='admin'))
        else:
            if db.scalar(select(Result).where(Result.title == '拉曼指针 · 演示成果')):
                print('演示数据已存在')
                return
            payload = MockAdapter().evaluate('拉曼指针 · 演示成果', ['拉曼指针', '拉曼', '光谱'], []).model_dump()
            payload['summary'] = '这是用于演示查询和页面布局的示例成果，不代表真实科研评价。'
            row = Result(title=payload['title'], search_text=search_text(payload), payload=payload, status='published')
            db.add(row)
            db.flush()
            db.add(ResultVersion(result_id=row.id, revision=1, payload=payload, editor='demo-seed'))
        db.commit()
        if args.command == 'create-admin' and args.generate_password:
            path = Path(__file__).resolve().parents[2] / '.local-access.md'
            path.write_text(f'# 本地管理员登录\n\nUsername: {args.username}\n\nPassword: {password}\n\n此文件仅用于本地开发，已加入 .gitignore。请妥善保管。\n', encoding='utf-8')
        print('完成')


if __name__ == '__main__':
    main()
