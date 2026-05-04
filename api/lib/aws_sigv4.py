"""AWS Signature Version 4 署名生成。

Why このモジュールを独立させるか:
    SigV4 は AWS 全般で使う汎用認証で PA-API 固有知識ではない。
    純粋関数として切り出すことでテスト容易性・凝集度・将来再利用性を確保し、
    1モジュール1責務原則を守る。

Why 標準ライブラリのみで実装するか:
    `boto3` / `botocore` 等の外部ライブラリは依存サイズが大きく、
    Vercel Serverless ランタイムでは小さい依存が望ましい。
    また、テストでロジック全体を検証可能にする目的（order.md 6節の方針）。
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Mapping


_ALGORITHM = "AWS4-HMAC-SHA256"
_TERMINATOR = "aws4_request"


def build_canonical_request(
    *,
    method: str,
    path: str,
    query: str,
    headers: Mapping[str, str],
    payload: bytes,
) -> str:
    """SigV4 Step 1: 正規リクエスト文字列を生成する。

    Why 各要素の整形仕様:
        - ヘッダ名は小文字化しアルファベット順に並べる（仕様）
        - 末尾はペイロードの SHA256 hex（GET の空ボディでも `e3b0...` を入れる）
    """
    canonical_headers = "".join(
        f"{name.lower()}:{value}\n"
        for name, value in sorted(headers.items(), key=lambda kv: kv[0].lower())
    )
    signed_headers = build_signed_headers(headers)
    payload_hash = hashlib.sha256(payload).hexdigest()
    return (
        f"{method}\n"
        f"{path}\n"
        f"{query}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )


def build_signed_headers(headers: Mapping[str, str]) -> str:
    """SignedHeaders 文字列（小文字 + アルファベット順、`;` 区切り）"""
    return ";".join(sorted(name.lower() for name in headers.keys()))


def build_string_to_sign(
    *,
    amz_date: str,
    date_stamp: str,
    region: str,
    service: str,
    canonical_request: str,
) -> str:
    """SigV4 Step 2: StringToSign を生成する。"""
    credential_scope = _credential_scope(date_stamp=date_stamp, region=region, service=service)
    cr_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    return f"{_ALGORITHM}\n{amz_date}\n{credential_scope}\n{cr_hash}"


def derive_signing_key(
    *,
    secret_key: str,
    date_stamp: str,
    region: str,
    service: str,
) -> bytes:
    """SigV4 Step 3: 派生鍵を `AWS4`+SecretKey → date → region → service → aws4_request の連鎖で生成する。

    Why この順序:
        AWS 仕様書で固定された連鎖順序であり、変更すると署名が一致しない。
    """
    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, _TERMINATOR)
    return k_signing


def compute_signature(*, signing_key: bytes, string_to_sign: str) -> str:
    """SigV4 Step 4: 最終署名を hex 文字列で得る。"""
    return hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def build_authorization_header(
    *,
    access_key: str,
    date_stamp: str,
    region: str,
    service: str,
    signed_headers: str,
    signature: str,
) -> str:
    """SigV4 Step 5: Authorization ヘッダ値を組み立てる。"""
    credential_scope = _credential_scope(date_stamp=date_stamp, region=region, service=service)
    return (
        f"{_ALGORITHM} "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )


def sign_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    payload: bytes,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    amz_datetime: str,
) -> str:
    """高レベル API: 入力リクエストから Authorization ヘッダ値（文字列）を返す。

    Why host を独立引数として受けない:
        host は SigV4 上 `Host` ヘッダとして headers に必ず含まれる必要があり、
        独立引数にすると同一値の二重指定になる。呼び出し元は headers["Host"] で渡す。
    """
    canonical_request = build_canonical_request(
        method=method,
        path=path,
        query="",
        headers=headers,
        payload=payload,
    )
    date_stamp = amz_datetime[:8]
    string_to_sign = build_string_to_sign(
        amz_date=amz_datetime,
        date_stamp=date_stamp,
        region=region,
        service=service,
        canonical_request=canonical_request,
    )
    signing_key = derive_signing_key(
        secret_key=secret_key,
        date_stamp=date_stamp,
        region=region,
        service=service,
    )
    signature = compute_signature(signing_key=signing_key, string_to_sign=string_to_sign)
    signed_headers = build_signed_headers(headers)
    return build_authorization_header(
        access_key=access_key,
        date_stamp=date_stamp,
        region=region,
        service=service,
        signed_headers=signed_headers,
        signature=signature,
    )


def _credential_scope(*, date_stamp: str, region: str, service: str) -> str:
    return f"{date_stamp}/{region}/{service}/{_TERMINATOR}"


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
