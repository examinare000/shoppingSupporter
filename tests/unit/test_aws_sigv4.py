"""AWS Signature Version 4 署名生成ロジックの単体テスト。

Why このテストを別ファイルで持つか:
    PA-API 5.0 の通信実装と AWS 認証ロジックは責務が異なる。SigV4 は AWS 全般で使う
    汎用認証であり、Amazon PA-API 固有知識ではない。Plan の 5.3 節「AWS Signature V4
    署名生成ロジックの単独テスト」要件を直接サポートする。

Why 期待値を直接ハードコードするか:
    AWS 公式テストベクター (`get-vanilla`) を期待値に採用する。
    自前のヘルパーで再計算してアサートすると「テストがプロダクションコードの実装を
    そのままなぞる」ことになり、検証にならない。AWS 公式の固定期待値で照合する。

Test Vector の出典:
    AWS Signature Version 4 公式ドキュメントの GET / IAM サンプル。
    AccessKey = AKIDEXAMPLE
    SecretKey = wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY
    Region    = us-east-1
    Service   = iam
    Date      = 20150830T123600Z
    Request   = GET /?Action=ListUsers&Version=2010-05-08

期待値（公式ドキュメントの Step 値と一致することを上記出典の手順で検算済み）:
    CanonicalRequest hash = f536975d06c0309214f805bb90ccff089219ecd68b2577efef23edd43b7e1a59
    SigningKey hex        = c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9
    Signature             = 5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7
"""

import hashlib

import pytest

# Why: 実装ステップで `api/lib/aws_sigv4.py` を新設する想定（plan 4.1）。
# 未実装段階では ImportError になるが、これは write_tests ステップでは想定内。
from api.lib import aws_sigv4


# AWS SigV4 公式 get-vanilla テストベクター
AWS_TV_ACCESS_KEY = "AKIDEXAMPLE"
AWS_TV_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
AWS_TV_REGION = "us-east-1"
AWS_TV_SERVICE = "iam"
AWS_TV_DATE_STAMP = "20150830"
AWS_TV_AMZ_DATE = "20150830T123600Z"

AWS_TV_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    "Host": "iam.amazonaws.com",
    "X-Amz-Date": AWS_TV_AMZ_DATE,
}
AWS_TV_METHOD = "GET"
AWS_TV_PATH = "/"
AWS_TV_QUERY = "Action=ListUsers&Version=2010-05-08"
AWS_TV_PAYLOAD = b""

AWS_TV_EXPECTED_CANONICAL_REQUEST = (
    "GET\n"
    "/\n"
    "Action=ListUsers&Version=2010-05-08\n"
    "content-type:application/x-www-form-urlencoded; charset=utf-8\n"
    "host:iam.amazonaws.com\n"
    "x-amz-date:20150830T123600Z\n"
    "\n"
    "content-type;host;x-amz-date\n"
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
AWS_TV_EXPECTED_CR_HASH = (
    "f536975d06c0309214f805bb90ccff089219ecd68b2577efef23edd43b7e1a59"
)
AWS_TV_EXPECTED_STRING_TO_SIGN = (
    "AWS4-HMAC-SHA256\n"
    "20150830T123600Z\n"
    "20150830/us-east-1/iam/aws4_request\n"
    "f536975d06c0309214f805bb90ccff089219ecd68b2577efef23edd43b7e1a59"
)
AWS_TV_EXPECTED_SIGNING_KEY_HEX = (
    "c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9"
)
AWS_TV_EXPECTED_SIGNATURE = (
    "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"
)
AWS_TV_EXPECTED_SIGNED_HEADERS = "content-type;host;x-amz-date"
AWS_TV_EXPECTED_AUTHORIZATION = (
    "AWS4-HMAC-SHA256 "
    "Credential=AKIDEXAMPLE/20150830/us-east-1/iam/aws4_request, "
    "SignedHeaders=content-type;host;x-amz-date, "
    "Signature=5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"
)


class TestBuildCanonicalRequest:
    """正規リクエスト生成: SigV4 仕様の Step 1 を検証する"""

    def test_aws_get_vanilla_vector(self):
        # Given: AWS 公式 get-vanilla テストベクターの入力
        # When: build_canonical_request を実行
        result = aws_sigv4.build_canonical_request(
            method=AWS_TV_METHOD,
            path=AWS_TV_PATH,
            query=AWS_TV_QUERY,
            headers=AWS_TV_HEADERS,
            payload=AWS_TV_PAYLOAD,
        )
        # Then: AWS 仕様どおりの正規リクエスト文字列が得られる
        assert result == AWS_TV_EXPECTED_CANONICAL_REQUEST

    def test_canonical_request_hash_matches(self):
        # Given: 上の正規リクエスト
        cr = aws_sigv4.build_canonical_request(
            method=AWS_TV_METHOD,
            path=AWS_TV_PATH,
            query=AWS_TV_QUERY,
            headers=AWS_TV_HEADERS,
            payload=AWS_TV_PAYLOAD,
        )
        # When: SHA256 ハッシュを取る
        cr_hash = hashlib.sha256(cr.encode()).hexdigest()
        # Then: 公式期待値と一致
        assert cr_hash == AWS_TV_EXPECTED_CR_HASH

    def test_headers_are_lowercased(self):
        # Given: 大文字混じりのヘッダ名
        headers = {"Host": "example.com", "X-Amz-Date": "20240101T000000Z"}
        # When
        cr = aws_sigv4.build_canonical_request(
            method="POST",
            path="/p",
            query="",
            headers=headers,
            payload=b"",
        )
        # Then: ヘッダ名は小文字化されている（SigV4 仕様）
        assert "host:example.com" in cr
        assert "x-amz-date:20240101T000000Z" in cr
        assert "Host:" not in cr
        assert "X-Amz-Date:" not in cr

    def test_headers_are_sorted_alphabetically(self):
        # Given: 順不同のヘッダ
        headers = {
            "X-Amz-Target": "Foo",
            "Host": "h.example.com",
            "Content-Encoding": "amz-1.0",
            "X-Amz-Date": "20240101T000000Z",
        }
        # When
        cr = aws_sigv4.build_canonical_request(
            method="POST", path="/p", query="", headers=headers, payload=b"",
        )
        # Then: アルファベット順に並ぶ
        lines = cr.split("\n")
        # method, path, query, then headers, then blank line, then signed_headers, hash
        header_lines = lines[3:7]
        names = [line.split(":", 1)[0] for line in header_lines]
        assert names == sorted(names)
        assert names == ["content-encoding", "host", "x-amz-date", "x-amz-target"]

    def test_payload_hash_for_empty_body(self):
        # Given: 空ボディ
        # When
        cr = aws_sigv4.build_canonical_request(
            method="GET", path="/", query="", headers={"Host": "h"}, payload=b"",
        )
        # Then: 末尾は SHA256("") の hex
        empty_hash = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        assert cr.endswith(empty_hash)

    def test_payload_hash_for_nonempty_body(self):
        # Given: 任意の JSON ボディ
        body = b'{"ItemIds":["B000"]}'
        expected_hash = hashlib.sha256(body).hexdigest()
        # When
        cr = aws_sigv4.build_canonical_request(
            method="POST",
            path="/paapi5/getitems",
            query="",
            headers={"Host": "webservices.amazon.co.jp"},
            payload=body,
        )
        # Then: ペイロードのハッシュが末尾に組み込まれる
        assert cr.endswith(expected_hash)


class TestBuildSignedHeaders:
    """SignedHeaders 文字列の組み立て"""

    def test_returns_lowercased_alphabetic_join(self):
        # Given
        headers = {
            "X-Amz-Target": "Foo",
            "Host": "h",
            "Content-Encoding": "amz-1.0",
            "X-Amz-Date": "20240101T000000Z",
        }
        # When
        signed = aws_sigv4.build_signed_headers(headers)
        # Then
        assert signed == "content-encoding;host;x-amz-date;x-amz-target"

    def test_get_vanilla_signed_headers(self):
        # Given: 公式テストベクターの 3 ヘッダ
        # When
        signed = aws_sigv4.build_signed_headers(AWS_TV_HEADERS)
        # Then
        assert signed == AWS_TV_EXPECTED_SIGNED_HEADERS


class TestBuildStringToSign:
    """SigV4 Step 2: StringToSign 生成"""

    def test_aws_get_vanilla_vector(self):
        # Given: 公式テストベクターの正規リクエスト
        # When
        sts = aws_sigv4.build_string_to_sign(
            amz_date=AWS_TV_AMZ_DATE,
            date_stamp=AWS_TV_DATE_STAMP,
            region=AWS_TV_REGION,
            service=AWS_TV_SERVICE,
            canonical_request=AWS_TV_EXPECTED_CANONICAL_REQUEST,
        )
        # Then: 公式期待値と一致
        assert sts == AWS_TV_EXPECTED_STRING_TO_SIGN

    def test_first_line_is_algorithm(self):
        # Given/When
        sts = aws_sigv4.build_string_to_sign(
            amz_date="20240101T000000Z",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
            canonical_request="dummy",
        )
        # Then: 1 行目はアルゴリズム識別子
        assert sts.split("\n")[0] == "AWS4-HMAC-SHA256"

    def test_third_line_is_credential_scope(self):
        # Given/When
        sts = aws_sigv4.build_string_to_sign(
            amz_date="20240101T000000Z",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
            canonical_request="dummy",
        )
        # Then: 3 行目は credential scope
        assert sts.split("\n")[2] == "20240101/us-west-2/ProductAdvertisingAPI/aws4_request"

    def test_fourth_line_is_canonical_request_hash(self):
        # Given: 任意の正規リクエスト
        cr = "some-canonical-request"
        expected_hash = hashlib.sha256(cr.encode()).hexdigest()
        # When
        sts = aws_sigv4.build_string_to_sign(
            amz_date="20240101T000000Z",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
            canonical_request=cr,
        )
        # Then: 4 行目は CR の SHA256
        assert sts.split("\n")[3] == expected_hash


class TestDeriveSigningKey:
    """SigV4 Step 3: 派生鍵の生成"""

    def test_aws_get_vanilla_vector(self):
        # Given: 公式テストベクターの認証情報
        # When
        key = aws_sigv4.derive_signing_key(
            secret_key=AWS_TV_SECRET_KEY,
            date_stamp=AWS_TV_DATE_STAMP,
            region=AWS_TV_REGION,
            service=AWS_TV_SERVICE,
        )
        # Then: 派生鍵の hex が公式期待値と一致
        assert key.hex() == AWS_TV_EXPECTED_SIGNING_KEY_HEX

    def test_returns_bytes(self):
        # Given/When
        key = aws_sigv4.derive_signing_key(
            secret_key="x",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
        )
        # Then: HMAC で使う bytes 型
        assert isinstance(key, bytes)
        assert len(key) == 32  # SHA-256 出力長


class TestComputeSignature:
    """SigV4 Step 4: 最終署名の生成"""

    def test_aws_get_vanilla_vector(self):
        # Given: 公式テストベクターの SigningKey と StringToSign
        signing_key = bytes.fromhex(AWS_TV_EXPECTED_SIGNING_KEY_HEX)
        # When
        signature = aws_sigv4.compute_signature(
            signing_key=signing_key,
            string_to_sign=AWS_TV_EXPECTED_STRING_TO_SIGN,
        )
        # Then: 公式期待値と一致
        assert signature == AWS_TV_EXPECTED_SIGNATURE

    def test_signature_is_lowercase_hex(self):
        # Given/When
        sig = aws_sigv4.compute_signature(
            signing_key=b"k" * 32,
            string_to_sign="x",
        )
        # Then: SigV4 仕様により小文字 hex
        assert sig == sig.lower()
        assert all(c in "0123456789abcdef" for c in sig)
        assert len(sig) == 64


class TestBuildAuthorizationHeader:
    """SigV4 Step 5: Authorization ヘッダ組み立て"""

    def test_aws_get_vanilla_vector(self):
        # Given: 公式テストベクター
        # When
        auth = aws_sigv4.build_authorization_header(
            access_key=AWS_TV_ACCESS_KEY,
            date_stamp=AWS_TV_DATE_STAMP,
            region=AWS_TV_REGION,
            service=AWS_TV_SERVICE,
            signed_headers=AWS_TV_EXPECTED_SIGNED_HEADERS,
            signature=AWS_TV_EXPECTED_SIGNATURE,
        )
        # Then: 公式期待値と一致
        assert auth == AWS_TV_EXPECTED_AUTHORIZATION

    def test_format_starts_with_algorithm(self):
        # Given/When
        auth = aws_sigv4.build_authorization_header(
            access_key="AK",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
            signed_headers="host",
            signature="abc",
        )
        # Then
        assert auth.startswith("AWS4-HMAC-SHA256 ")

    def test_contains_credential_signedheaders_signature_segments(self):
        # Given/When
        auth = aws_sigv4.build_authorization_header(
            access_key="AK",
            date_stamp="20240101",
            region="us-west-2",
            service="ProductAdvertisingAPI",
            signed_headers="content-encoding;host;x-amz-date;x-amz-target",
            signature="deadbeef",
        )
        # Then: 仕様で要求される 3 セクションを含む
        assert "Credential=AK/20240101/us-west-2/ProductAdvertisingAPI/aws4_request" in auth
        assert "SignedHeaders=content-encoding;host;x-amz-date;x-amz-target" in auth
        assert "Signature=deadbeef" in auth


class TestSignRequestEndToEnd:
    """sign_request で「リクエスト → Authorization ヘッダ値（文字列）」が組める

    PA-API 5.0 想定のパラメータ（POST + JSON + ProductAdvertisingAPI/us-west-2）で
    エンドツーエンド検証する。期待値は別プロセスで再現性を担保するため、テスト内で
    inputs から独立に再計算するのではなく、上で検証済みの 5 ステップが結合された
    結果として整合することを確認する。
    """

    def test_returns_authorization_header_with_correct_credential_scope(self, amazon_env):
        # Given: PA-API GetItems の入力
        # When
        auth = aws_sigv4.sign_request(
            method="POST",
            path="/paapi5/getitems",
            headers={
                "Host": "webservices.amazon.co.jp",
                "Content-Encoding": "amz-1.0",
                "X-Amz-Date": "20240101T000000Z",
                "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
            },
            payload=b'{"x":1}',
            access_key=amazon_env["access_key"],
            secret_key=amazon_env["secret_key"],
            region="us-west-2",
            service="ProductAdvertisingAPI",
            amz_datetime="20240101T000000Z",
        )
        # Then: Authorization ヘッダ値が文字列で返り、credential scope が PA-API JP 用
        assert auth.startswith("AWS4-HMAC-SHA256 ")
        assert (
            "Credential="
            f"{amazon_env['access_key']}/20240101/us-west-2/ProductAdvertisingAPI/aws4_request"
        ) in auth
        assert (
            "SignedHeaders=content-encoding;host;x-amz-date;x-amz-target" in auth
        )

    def test_signature_is_deterministic_for_same_inputs(self, amazon_env):
        # Given: 同一入力
        kwargs = dict(
            method="POST",
            path="/paapi5/getitems",
            headers={
                "Host": "webservices.amazon.co.jp",
                "Content-Encoding": "amz-1.0",
                "X-Amz-Date": "20240101T000000Z",
                "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
            },
            payload=b'{"x":1}',
            access_key=amazon_env["access_key"],
            secret_key=amazon_env["secret_key"],
            region="us-west-2",
            service="ProductAdvertisingAPI",
            amz_datetime="20240101T000000Z",
        )
        # When: 二度呼ぶ
        a = aws_sigv4.sign_request(**kwargs)
        b = aws_sigv4.sign_request(**kwargs)
        # Then: SigV4 は決定的なので一致
        assert a == b

    def test_different_payload_yields_different_signature(self, amazon_env):
        # Given: payload のみ異なる
        base = dict(
            method="POST",
            path="/paapi5/getitems",
            headers={
                "Host": "webservices.amazon.co.jp",
                "Content-Encoding": "amz-1.0",
                "X-Amz-Date": "20240101T000000Z",
                "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
            },
            access_key=amazon_env["access_key"],
            secret_key=amazon_env["secret_key"],
            region="us-west-2",
            service="ProductAdvertisingAPI",
            amz_datetime="20240101T000000Z",
        )
        # When
        sig_a = aws_sigv4.sign_request(payload=b'{"a":1}', **base)
        sig_b = aws_sigv4.sign_request(payload=b'{"b":2}', **base)
        # Then
        assert sig_a != sig_b
