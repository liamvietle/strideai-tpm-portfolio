"""Operator-only password recovery. Run on the server with its production DB path."""
import getpass
import sys
from app.accounts import init_accounts, password_hash
from app.storage import connect


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m app.account_admin USERNAME')
    init_accounts()
    username=sys.argv[1].lower()
    with connect() as c:
        row=c.execute('SELECT id FROM accounts WHERE username=?',(username,)).fetchone()
    if not row:
        raise SystemExit('Account not found.')
    password=getpass.getpass('New password (12–128 characters): ')
    if not 12 <= len(password) <= 128 or password != getpass.getpass('Confirm password: '):
        raise SystemExit('Password length or confirmation does not match.')
    hashed=password_hash(password)
    with connect() as c:
        c.execute('UPDATE accounts SET password_hash=? WHERE id=?',(hashed,row['id']))
        c.execute('DELETE FROM account_sessions WHERE account_id=?',(row['id'],))
        c.execute('DELETE FROM account_devices WHERE account_id=?',(row['id'],))
    print('Password reset. All sessions and Apple Health device keys for this account were revoked.')


if __name__=='__main__':
    main()
