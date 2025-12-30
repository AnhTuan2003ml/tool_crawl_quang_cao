#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sterilization.py
----------------
Gộp nhiều file Excel (.xlsx) có cùng định dạng và lọc trùng theo "ID User"
(bỏ qua "ID Bài Post" khi xét trùng).

Ví dụ:
    python sterilization.py a.xlsx b.xlsx c.xlsx -o out.xlsx

Nếu không truyền -o, script sẽ tạo file output theo thời gian.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd


# Các tên cột có thể gặp (normalize về lowercase, bỏ khoảng trắng/thừa)
USER_ID_CANDIDATES = {
    "id user",
    "id_user",
    "userid",
    "user id",
    "uid",
    "id người dùng",
    "id nguoi dung",
}

POST_ID_CANDIDATES = {
    "id bài post",
    "id bai post",
    "id post",
    "post id",
    "id_post",
    "postid",
}


def _norm_col(s: str) -> str:
    return " ".join(str(s).strip().lower().replace("_", " ").split())


def detect_columns(df: pd.DataFrame) -> Tuple[str, Optional[str]]:
    """
    Trả về (user_id_col, post_id_col|None)
    """
    norm_map = {c: _norm_col(c) for c in df.columns}

    user_id_col = None
    post_id_col = None

    for c, nc in norm_map.items():
        if nc in USER_ID_CANDIDATES and user_id_col is None:
            user_id_col = c
        if nc in POST_ID_CANDIDATES and post_id_col is None:
            post_id_col = c

    if user_id_col is None:
        # gợi ý cột gần giống
        hint = ", ".join([str(c) for c in df.columns])
        raise ValueError(
            f"Không tìm thấy cột ID User. Các cột đang có: {hint}\n"
            f"Bạn hãy đảm bảo file có cột 'ID User' (hoặc biến thể tương đương)."
        )

    return user_id_col, post_id_col


def read_xlsx(path: str, sheet: Optional[str] = None) -> pd.DataFrame:
    """
    Đọc xlsx, ưu tiên sheet đầu nếu không chỉ định.
    """
    try:
        if sheet is None:
            df = pd.read_excel(path)  # sheet đầu
        else:
            df = pd.read_excel(path, sheet_name=sheet)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc file: {path}\n{e}") from e


def dedupe_by_user_id(frames: List[pd.DataFrame], user_id_col: str) -> pd.DataFrame:
    """
    Lọc trùng theo ID User bằng set, giữ thứ tự xuất hiện (ổn định).
    """
    seen = set()
    kept_rows = []

    for df in frames:
        if df is None or df.empty:
            continue

        # Giữ nguyên kiểu dữ liệu; nhưng ID thường là số dài => convert string để so sánh chắc chắn
        for _, row in df.iterrows():
            uid = row.get(user_id_col, None)
            if pd.isna(uid):
                continue
            uid_str = str(uid).strip()
            if not uid_str:
                continue
            if uid_str in seen:
                continue
            seen.add(uid_str)
            kept_rows.append(row)

    if not kept_rows:
        return pd.DataFrame()

    return pd.DataFrame(kept_rows)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gộp nhiều file xlsx và lọc trùng theo ID User (không cần ID Bài Post)."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Danh sách đường dẫn file .xlsx (có thể truyền nhiều file).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Đường dẫn file output .xlsx. Nếu bỏ trống sẽ tự đặt tên theo thời gian.",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Tên sheet cần đọc (mặc định: sheet đầu tiên).",
    )
    parser.add_argument(
        "--keep-post-id-col",
        action="store_true",
        help="Giữ nguyên cột ID Bài Post trong output (mặc định: có, vì giữ đúng format input).",
    )

    args = parser.parse_args(argv)

    # Chuẩn hoá input paths
    input_paths = []
    for p in args.inputs:
        p2 = os.path.abspath(p)
        if not os.path.isfile(p2):
            print(f"[WARN] Không thấy file: {p}", file=sys.stderr)
            continue
        if not p2.lower().endswith(".xlsx"):
            print(f"[WARN] Bỏ qua (không phải .xlsx): {p}", file=sys.stderr)
            continue
        input_paths.append(p2)

    if not input_paths:
        print("Không có file .xlsx hợp lệ để xử lý.", file=sys.stderr)
        return 2

    # Đọc các file
    frames = []
    user_id_col = None
    post_id_col = None

    for p in input_paths:
        df = read_xlsx(p, sheet=args.sheet)
        if df.empty:
            print(f"[INFO] File rỗng: {p}")
            continue

        ucol, pcol = detect_columns(df)

        # Đảm bảo cùng cột ID User giữa các file (theo tên cột), nếu khác thì vẫn dùng cột của từng file
        # Tuy nhiên để output đồng nhất, ta sẽ ưu tiên cột ID User của file đầu tiên.
        if user_id_col is None:
            user_id_col, post_id_col = ucol, pcol

        # Nếu file sau dùng tên cột khác, đổi về tên chuẩn theo file đầu tiên
        if ucol != user_id_col:
            df = df.rename(columns={ucol: user_id_col})
        if post_id_col is not None and pcol is not None and pcol != post_id_col:
            df = df.rename(columns={pcol: post_id_col})

        frames.append(df)

    if not frames:
        print("Tất cả file đều rỗng hoặc không đọc được.", file=sys.stderr)
        return 2

    merged = dedupe_by_user_id(frames, user_id_col=user_id_col)

    if merged.empty:
        print("Không có dòng hợp lệ sau khi lọc.", file=sys.stderr)
        return 3

    # Mặc định: vẫn giữ nguyên format input (bao gồm cột ID Bài Post nếu có)
    # Nếu user muốn bỏ hẳn cột ID Bài Post khỏi output, có thể tự xóa sau, hoặc sửa đây.
    if not args.keep_post_id_col and post_id_col in merged.columns:
        merged = merged.drop(columns=[post_id_col])

    # Output
    if args.output:
        out_path = os.path.abspath(args.output)
        if not out_path.lower().endswith(".xlsx"):
            out_path += ".xlsx"
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.abspath(f"sterilized_{ts}.xlsx")

    # Ghi file
    try:
        merged.to_excel(out_path, index=False)
    except Exception as e:
        print(f"Lỗi ghi output: {out_path}\n{e}", file=sys.stderr)
        return 4

    total_in = sum(len(df) for df in frames if df is not None)
    total_out = len(merged)
    print("✅ Done")
    print(f"Input files : {len(input_paths)}")
    print(f"Rows in     : {total_in}")
    print(f"Rows out    : {total_out}")
    print(f"Output      : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
