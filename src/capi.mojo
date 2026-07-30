from std.sys.info import simd_width_of


comptime BPtr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime IPtr = UnsafePointer[Int, AnyOrigin[mut=True]]


def is_space(c: UInt8) -> Bool:
    return c == 9 or c == 10 or c == 12 or c == 32


def is_alpha(c: UInt8) -> Bool:
    return (c >= 65 and c <= 90) or (c >= 97 and c <= 122)


def is_digit(c: UInt8) -> Bool:
    return c >= 48 and c <= 57


def is_name(c: UInt8) -> Bool:
    return is_alpha(c) or is_digit(c) or c == 45 or c == 58 or c == 95


def lower(c: UInt8) -> UInt8:
    if c >= 65 and c <= 90:
        return c + 32
    return c


def matches(src: BPtr, pos: Int, n: Int, a: UInt8, b: UInt8) -> Bool:
    return pos + 1 < n and src[pos] == a and src[pos + 1] == b


def is_stateful_tag(src: BPtr, begin: Int, finish: Int) -> Bool:
    var length = finish - begin
    if length == 3:
        return lower(src[begin]) == 120 and lower(src[begin + 1]) == 109 and
            lower(src[begin + 2]) == 112
    if length == 4:
        return lower(src[begin]) == 109 and lower(src[begin + 1]) == 101 and
            lower(src[begin + 2]) == 116 and lower(src[begin + 3]) == 97
    if length == 5:
        var last_four = lower(src[begin + 1]) == 116 and lower(src[begin + 2]) == 121 and
            lower(src[begin + 3]) == 108 and lower(src[begin + 4]) == 101
        return (lower(src[begin]) == 115 and last_four) or (
            lower(src[begin]) == 116 and lower(src[begin + 1]) == 105 and
            lower(src[begin + 2]) == 116 and lower(src[begin + 3]) == 108 and
            lower(src[begin + 4]) == 101
        )
    if length == 6:
        return (
            lower(src[begin]) == 115 and lower(src[begin + 1]) == 99 and
            lower(src[begin + 2]) == 114 and lower(src[begin + 3]) == 105 and
            lower(src[begin + 4]) == 112 and lower(src[begin + 5]) == 116
        ) or (
            lower(src[begin]) == 105 and lower(src[begin + 1]) == 102 and
            lower(src[begin + 2]) == 114 and lower(src[begin + 3]) == 97 and
            lower(src[begin + 4]) == 109 and lower(src[begin + 5]) == 101
        )
    if length == 7:
        return lower(src[begin]) == 110 and lower(src[begin + 1]) == 111 and
            lower(src[begin + 2]) == 101 and lower(src[begin + 3]) == 109 and
            lower(src[begin + 4]) == 98 and lower(src[begin + 5]) == 101 and
            lower(src[begin + 6]) == 100
    if length == 8:
        var no_prefix = lower(src[begin]) == 110 and lower(src[begin + 1]) == 111
        return no_prefix and (
            (
                lower(src[begin + 2]) == 102 and lower(src[begin + 3]) == 114 and
                lower(src[begin + 4]) == 97 and lower(src[begin + 5]) == 109 and
                lower(src[begin + 6]) == 101 and lower(src[begin + 7]) == 115
            ) or (
                lower(src[begin + 2]) == 115 and lower(src[begin + 3]) == 99 and
                lower(src[begin + 4]) == 114 and lower(src[begin + 5]) == 105 and
                lower(src[begin + 6]) == 112 and lower(src[begin + 7]) == 116
            )
        ) or (
            lower(src[begin]) == 116 and lower(src[begin + 1]) == 101 and
            lower(src[begin + 2]) == 120 and lower(src[begin + 3]) == 116 and
            lower(src[begin + 4]) == 97 and lower(src[begin + 5]) == 114 and
            lower(src[begin + 6]) == 101 and lower(src[begin + 7]) == 97
        )
    if length == 9:
        return lower(src[begin]) == 112 and lower(src[begin + 1]) == 108 and
            lower(src[begin + 2]) == 97 and lower(src[begin + 3]) == 105 and
            lower(src[begin + 4]) == 110 and lower(src[begin + 5]) == 116 and
            lower(src[begin + 6]) == 101 and lower(src[begin + 7]) == 120 and
            lower(src[begin + 8]) == 116
    return False


def scan_impl(src: BPtr, rec: IPtr, n: Int, write: Bool) -> Int:
    comptime W = simd_width_of[DType.uint8]()
    var i = 0
    var rows = 0
    while i < n:
        var c = src[i]
        if c == 0 or c == 13 or c >= 128:
            return -1

        if c == 38:
            var j = i + 1
            if j >= n:
                return -1
            if src[j] == 35:
                j += 1
                if j < n and (src[j] == 120 or src[j] == 88):
                    j += 1
                    var begin = j
                    while j < n and ((src[j] >= 48 and src[j] <= 57) or
                                     (src[j] >= 65 and src[j] <= 70) or
                                     (src[j] >= 97 and src[j] <= 102)):
                        j += 1
                    if j == begin:
                        return -1
                else:
                    var begin = j
                    while j < n and is_digit(src[j]):
                        j += 1
                    if j == begin:
                        return -1
            else:
                var begin = j
                while j < n and (is_alpha(src[j]) or is_digit(src[j])):
                    j += 1
                if j == begin:
                    return -1
            if j >= n or src[j] != 59:
                return -1
            if write:
                rec[rows * 5] = 10
                rec[rows * 5 + 1] = i
                rec[rows * 5 + 2] = j + 1
                rec[rows * 5 + 3] = 0
                rec[rows * 5 + 4] = 0
            rows += 1
            i = j + 1
            continue

        if c != 60:
            var j = i
            var kind: Int = 1
            if is_space(c):
                kind = 2
                while j < n and is_space(src[j]):
                    j += 1
            else:
                while j + W <= n:
                    var v = src.load[width=W](j)
                    var stop = v.eq(SIMD[DType.uint8, W](38)) | v.eq(
                        SIMD[DType.uint8, W](60)
                    ) | v.eq(SIMD[DType.uint8, W](0)) | v.eq(
                        SIMD[DType.uint8, W](13)
                    ) | v.ge(SIMD[DType.uint8, W](128))
                    if stop.reduce_or():
                        break
                    j += W
                while j < n and src[j] != 38 and src[j] != 60:
                    if src[j] == 0 or src[j] == 13 or src[j] >= 128:
                        return -1
                    j += 1
            if write:
                rec[rows * 5] = kind
                rec[rows * 5 + 1] = i
                rec[rows * 5 + 2] = j
                rec[rows * 5 + 3] = 0
                rec[rows * 5 + 4] = 0
            rows += 1
            i = j
            continue

        if i + 3 < n and src[i + 1] == 33 and src[i + 2] == 45 and src[i + 3] == 45:
            var j = i + 4
            while j + 2 < n and not (src[j] == 45 and src[j + 1] == 45 and src[j + 2] == 62):
                if src[j] == 0 or src[j] == 13 or src[j] >= 128:
                    return -1
                if src[j] == 45 and src[j + 1] == 45:
                    return -1
                j += 1
            if j + 2 >= n:
                return -1
            if write:
                rec[rows * 5] = 6
                rec[rows * 5 + 1] = i + 4
                rec[rows * 5 + 2] = j
                rec[rows * 5 + 3] = 0
                rec[rows * 5 + 4] = 0
            rows += 1
            i = j + 3
            continue

        if i + 9 < n and src[i + 1] == 33:
            var good = True
            if lower(src[i + 2]) != 100 or lower(src[i + 3]) != 111 or
               lower(src[i + 4]) != 99 or lower(src[i + 5]) != 116 or
               lower(src[i + 6]) != 121 or lower(src[i + 7]) != 112 or
               lower(src[i + 8]) != 101:
                good = False
            if good and is_space(src[i + 9]):
                var j = i + 10
                while j < n and is_space(src[j]):
                    j += 1
                var begin = j
                while j < n and is_name(src[j]):
                    j += 1
                if j == begin:
                    return -1
                var finish = j
                while j < n and is_space(src[j]):
                    j += 1
                if j >= n or src[j] != 62:
                    return -1
                if write:
                    rec[rows * 5] = 0
                    rec[rows * 5 + 1] = begin
                    rec[rows * 5 + 2] = finish
                    rec[rows * 5 + 3] = 0
                    rec[rows * 5 + 4] = 0
                rows += 1
                i = j + 1
                continue

        var closing = False
        var j = i + 1
        if j < n and src[j] == 47:
            closing = True
            j += 1
        if j >= n or not is_alpha(src[j]):
            return -1
        var name_begin = j
        while j < n and is_name(src[j]):
            j += 1
        var name_finish = j

        if not closing and is_stateful_tag(src, name_begin, name_finish):
            return -1

        if closing:
            while j < n and is_space(src[j]):
                j += 1
            if j >= n or src[j] != 62:
                return -1
            if write:
                rec[rows * 5] = 4
                rec[rows * 5 + 1] = name_begin
                rec[rows * 5 + 2] = name_finish
                rec[rows * 5 + 3] = 0
                rec[rows * 5 + 4] = 0
            rows += 1
            i = j + 1
            continue

        var tag_row = rows
        if write:
            rec[rows * 5] = 3
            rec[rows * 5 + 1] = name_begin
            rec[rows * 5 + 2] = name_finish
            rec[rows * 5 + 3] = 0
            rec[rows * 5 + 4] = 0
        rows += 1
        var self_closing: Int = 0
        while True:
            while j < n and is_space(src[j]):
                j += 1
            if j >= n:
                return -1
            if src[j] == 62:
                j += 1
                break
            if matches(src, j, n, 47, 62):
                self_closing = 1
                j += 2
                break
            if not is_name(src[j]):
                return -1
            var attr_begin = j
            while j < n and is_name(src[j]):
                j += 1
            var attr_finish = j
            while j < n and is_space(src[j]):
                j += 1
            var value_begin = j
            var value_finish = j
            if j < n and src[j] == 61:
                j += 1
                while j < n and is_space(src[j]):
                    j += 1
                if j >= n:
                    return -1
                if src[j] == 34 or src[j] == 39:
                    var quote = src[j]
                    j += 1
                    value_begin = j
                    while j + W <= n:
                        var v = src.load[width=W](j)
                        var stop = v.eq(SIMD[DType.uint8, W](quote)) | v.eq(
                            SIMD[DType.uint8, W](0)
                        ) | v.eq(SIMD[DType.uint8, W](13)) | v.ge(
                            SIMD[DType.uint8, W](128)
                        )
                        if stop.reduce_or():
                            break
                        j += W
                    while j < n and src[j] != quote:
                        if src[j] == 0 or src[j] == 13 or src[j] >= 128:
                            return -1
                        j += 1
                    if j >= n:
                        return -1
                    value_finish = j
                    j += 1
                else:
                    value_begin = j
                    while j < n and not is_space(src[j]) and src[j] != 62:
                        if src[j] == 0 or src[j] == 13 or src[j] >= 128 or
                           src[j] == 34 or src[j] == 39 or src[j] == 60 or src[j] == 61:
                            return -1
                        j += 1
                    if j == value_begin:
                        return -1
                    value_finish = j
            if write:
                rec[rows * 5] = 8
                rec[rows * 5 + 1] = attr_begin
                rec[rows * 5 + 2] = attr_finish
                rec[rows * 5 + 3] = value_begin
                rec[rows * 5 + 4] = value_finish
            rows += 1
        if write:
            rec[tag_row * 5 + 3] = self_closing
        i = j
    return rows


@export("mh5_scan")
def mh5_scan(src_addr: Int, n: Int, records_addr: Int, capacity: Int) abi("C") -> Int:
    if n < 0 or capacity < 0:
        return -2
    if n == 0:
        return 0
    if src_addr == 0:
        return -2
    var src = BPtr(unsafe_from_address=src_addr)
    if records_addr == 0:
        var dummy = IPtr(unsafe_from_address=src_addr)
        return scan_impl(src, dummy, n, False)
    var dummy = IPtr(unsafe_from_address=src_addr)
    var required = scan_impl(src, dummy, n, False)
    if required < 0:
        return required
    if required > capacity:
        return -2
    var records = IPtr(unsafe_from_address=records_addr)
    return scan_impl(src, records, n, True)
