#
# Search operations
#
# Copyright (c) 2018, Nobutaka Mantani
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import binascii
import ctypes
import os
import re
import subprocess
import string
import sys
import tempfile
import time

def bookmark_yesno_dialog(num_bookmark):
    """
    Show a confirmation dialog of adding many bookmarks
    """
    # Do not show command prompt window
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute bookmark_yesno_dialog.py to show confirmation dialog
    p = subprocess.Popen(["py.exe", "-3", "Misc/bookmark_yesno_dialog.py", str(num_bookmark)], startupinfo=startupinfo, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # Receive scan result
    stdout_data, stderr_data = p.communicate()
    ret = p.wait()

    return ret

def mask(x):
    """
    Masking bits
    Used by xor_hex_search() and xor_text_search()
    """
    if x >= 0:
        return 2 ** x - 1
    else:
        return 0

def ror(x, rot=1):
    """
    Bitwise rotate right
    Used by xor_hex_search() and xor_text_search()
    """
    rot %= 8
    if rot < 1:
        return x
    x &= mask(8)
    return (x >> rot) | ((x << (8 - rot)) & mask(8))

def rol(x, rot=1):
    """
    Bitwise rotate left
    Used by xor_hex_search() and xor_text_search()
    """
    rot %= 8
    if rot < 1:
        return x
    x &= mask(8)
    return ((x << rot) & mask(8)) | (x >> (8 - rot))

def valdict(data):
    """
    Make dictionary of values in data
    Used by xor_hex_search() and xor_text_search()
    """
    values = {}
    b = list(data)
    length = len(b)

    for i in range(0, length):
        v = ord(data[i])
        if v not in values:
            values[v] = True

    return values

def search_xor_rol_hex(fi, data, offset, length, keyword):
    """
    Search XORed and bit-rotated string
    Used by xor_hex_search()
    """
    LEN_AFTER_HIT = 30

    values = valdict(data)
    num_hits = 0
    output = ""
    bookmark_list = []

    for i in range(0, 8):
        for j in range(0, 256):
            pattern = keyword[:]
            notinvalues = False
            hits = []

            # Encode search string and check whether the values of encoded string exist in data
            for k in range(0, len(pattern)):
                pattern[k] = chr(ror(ord(pattern[k]), i) ^ j)
                if ord(pattern[k]) not in values:
                    notinvalues = True
                    break

            # Skip search if the values of encoded string don't exist in data
            if notinvalues:
                continue

            pos = data.find("".join(pattern), 0)

            if pos != -1:
                hits.append(pos)

            while pos != -1:
                pos = data.find("".join(pattern), pos + len(pattern))
                if pos != -1:
                    hits.append(pos)

            # Print search hits
            for k in hits:
                end = k + len(pattern) + LEN_AFTER_HIT
                if end < length:
                    hitstr = list(data[k:end])
                else:
                    hitstr = list(data[k:])

                for l in range(0, len(hitstr)):
                    c = rol(ord(hitstr[l]) ^ j, i)
                    hitstr[l] = chr(c)

                hitstr = binascii.hexlify("".join(hitstr))
                hitstr = hitstr.upper()
                output += "XOR key: 0x%02x -> ROL bit: %d offset: 0x%x search hit: %s\n" % (j, i, offset + k, "".join(hitstr))
                bookmark_list.append((offset + k, len(keyword)))
                num_hits += 1

    if output != "":
        print(output)

    if num_hits > 100 and not bookmark_yesno_dialog(num_hits):
        do_bookmark = False
    else:
        do_bookmark = True

    if do_bookmark:
        for (i, j) in bookmark_list:
            fi.setBookmark(i, j, hex(i), "#aaffaa")

        if num_hits == 1:
            print("Added a bookmark to the search hit.")
        elif num_hits > 1:
            print("Added bookmarks to the search hits.")

    return num_hits

def xor_hex_search(fi):
    """
    Search XORed / bit-rotated data in selected region (the whole file if not selected)
    """
    if fi.getDocumentCount() == 0:
        return

    length_sel = fi.getSelectionLength()
    offset = fi.getSelectionOffset()
    keyword = fi.showSimpleDialog("Search keyword (in hex):")
    keyword = keyword.replace("0x", "")

    try:
        dummy = int(keyword, 16)
    except:
        print("Error: search keyword is not hexadecimal.")
        return

    disp_keyword = "0x" + keyword.lower()
    keyword = list(binascii.unhexlify(keyword))

    if len(keyword) > 0:
        if length_sel > 0:
            length = length_sel
            data = fi.getSelection()
            print("Search XORed / bit-rotated data from offset %s to %s with keyword %s" % (hex(offset), hex(offset + length - 1), disp_keyword))
        else:
            data = fi.getDocument()
            length = fi.getLength()
            offset = 0
            print("Search XORed / bit-rotated data in the whole file with keyword %s" % disp_keyword)

        num_hit = search_xor_rol_hex(fi, data, offset, length, keyword)

def search_xor_rol_text(fi, data, offset, length, keyword):
    """
    Search XORed and bit-rotated string
    Used by xor_text_search()
    """
    LEN_AFTER_HIT = 50

    values = valdict(data)
    num_hits = 0
    output = ""
    bookmark_list = []

    for i in range(0, 8):
        for j in range(0, 256):
            pattern = keyword[:]
            notinvalues = False
            hits = []

            # Encode search string and check whether the values of encoded string exist in data
            for k in range(0, len(pattern)):
                pattern[k] = chr(ror(ord(pattern[k]), i) ^ j)
                if ord(pattern[k]) not in values:
                    notinvalues = True
                    break

            # Skip search if the values of encoded string don't exist in data
            if notinvalues:
                continue

            pos = data.find("".join(pattern), 0)

            if pos != -1:
                hits.append(pos)

            while pos != -1:
                pos = data.find("".join(pattern), pos + len(pattern))
                if pos != -1:
                    hits.append(pos)

            # Print search hits
            for k in hits:
                end = k + len(pattern) + LEN_AFTER_HIT
                if end < length:
                    hitstr = list(data[k:end])
                else:
                    hitstr = list(data[k:])

                for l in range(0, len(hitstr)):
                    c = rol(ord(hitstr[l]) ^ j, i)
                    if c < 0x20 or c > 0x126:
                        c = 0x2e
                    hitstr[l] = chr(c)

                output += "XOR key: 0x%02x -> ROL bit: %d offset: 0x%x search hit: %s\n" % (j, i, offset + k, "".join(hitstr))
                bookmark_list.append((offset + k, len(keyword)))
                num_hits += 1

    if output != "":
        print(output)

    if num_hits > 100 and not bookmark_yesno_dialog(num_hits):
        do_bookmark = False
    else:
        do_bookmark = True

    if do_bookmark:
        for (i, j) in bookmark_list:
            fi.setBookmark(i, j, hex(i), "#aaffaa")

        if num_hits == 1:
            print("Added a bookmark to the search hit.")
        elif num_hits > 1:
            print("Added bookmarks to the search hits.")

    return num_hits

def xor_text_search(fi):
    """
    Search XORed / bit-rotated string in selected region (the whole file if not selected)
    """
    if fi.getDocumentCount() == 0:
        return

    length_sel = fi.getSelectionLength()
    offset = fi.getSelectionOffset()
    keyword = list(fi.showSimpleDialog("Search keyword:"))

    if len(keyword) > 0:
        if length_sel > 0:
            length = length_sel
            data = fi.getSelection()
            print("Search XORed / bit-rotated string from offset %s to %s with keyword '%s'" % (hex(offset), hex(offset + length - 1), "".join(keyword)))
        else:
            data = fi.getDocument()
            length = fi.getLength()
            offset = 0
            print("Search XORed / bit-rotated string in the whole file with keyword '%s'" % "".join(keyword))
        num_hit = search_xor_rol_text(fi, data, offset, length, keyword)

def is_printable(s):
    """
    Return True if 's' is printable string
    Used by regex_search(), replace() and yara_scan()
    """
    try:
        return all(c in string.printable for c in s)
    except TypeError:
        return False

def regex_search(fi):
    """
    Search with regular expression in selected region (the whole file if not selected)
    """
    if fi.getDocumentCount() == 0:
        return

    length_sel = fi.getSelectionLength()
    offset = fi.getSelectionOffset()
    if length_sel > 0:
        length = length_sel
        data = fi.getSelection()
    else:
        data = fi.getDocument()
        length = fi.getLength()
        offset = 0

    if data == "":
        return

    keyword = fi.showSimpleDialog("Regular expression (please see https://docs.python.org/2.7/library/re.html for syntax):")

    time_start = time.time()

    if len(keyword) > 0:
        if length_sel > 0:
            print("Search from offset %s to %s with keyword '%s'" % (hex(offset), hex(offset + length - 1), keyword))
        else:
            print("Search in the whole file with keyword '%s'" % keyword)

        try:
            re.compile(keyword)
        except:
            print("Error: invalid regular expression")
            return

        num_hits = 0
        match = re.finditer(keyword, data)
        bookmark_start = []
        bookmark_end = []
        output = ""
        for m in match:
            if is_printable(m.group()):
                output += "Offset: 0x%x Search hit: %s\n" % (offset + m.start(), re.sub("[\r\n\v\f]", "", m.group()))
            else:
                output += "Offset: 0x%x Search hit: %s (hex)\n" % (offset + m.start(), binascii.hexlify(m.group()))
            if num_hits > 0 and offset + m.start() == bookmark_end[-1]:
                bookmark_end[-1] = offset + m.end()
            else:
                bookmark_start.append(offset + m.start())
                bookmark_end.append(offset + m.end())
            num_hits += 1

        if output != "":
            print(output)

        print("Elapsed time (search): %f (sec)" % (time.time() - time_start))
        time_start = time.time()

        if num_hits > 100 and not bookmark_yesno_dialog(num_hits):
            do_bookmark = False
        else:
            do_bookmark = True

        if do_bookmark:
            for i in range(0, len(bookmark_start)):
                fi.setBookmark(bookmark_start[i], bookmark_end[i] - bookmark_start[i], hex(bookmark_start[i]), "#aaffaa")

            if num_hits == 1:
                print("Added a bookmark to the search hit.")
            elif num_hits > 1:
                print("Added bookmarks to the search hits.")

            print("Elapsed time (bookmark): %f (sec)" % (time.time() - time_start))

def replace(fi):
    """
    Replace matched data in selected region (the whole file if not selected) with specified data
    """
    if fi.getDocumentCount() == 0:
        return

    length_sel = fi.getSelectionLength()
    offset = fi.getSelectionOffset()

    if length_sel > 0:
        length = length_sel
        data = fi.getSelection()
    else:
        data = fi.getDocument()
        length = fi.getLength()
        offset = 0

    if data == "":
        return

    # Do not show command prompt window
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute send_to.py to show GUI
    # GUI portion is moved to send_to.py to avoid hangup of FileInsight
    p = subprocess.Popen(["py.exe", "-3", "Search/replace_dialog.py"], startupinfo=startupinfo, stdout=subprocess.PIPE)

    stdout_data, stderr_data = p.communicate()
    if stdout_data == "":
        return
    else:
        (keyword, replacement, mode, dummy) = stdout_data.split("\r\n")
        if keyword == "":
            return
        if mode == "Text":
            replacement_data = list(replacement)
        elif mode == "Hex":
            replacement_data = list(binascii.unhexlify(replacement))
        else:
            return
        replacement_len = len(replacement_data)

    time_start = time.time()

    if len(keyword) > 0:
        if length_sel > 0:
            print("Replace from offset %s to %s with keyword '%s' and replacement '%s'" % (hex(offset), hex(offset + length - 1), keyword, replacement))
        else:
            print("Replace in the whole file with keyword '%s' and replacement '%s'" % (keyword, replacement))

        try:
            re.compile(keyword)
        except:
            print("Error: invalid regular expression")
            return

        data_list_all = list(fi.getDocument())
        data_all_len = fi.getLength()
        if offset == 0:
            new_data = []
        if offset > 0:
            new_data = data_list_all[:offset]

        num_hits = 0
        prev_pos = 0
        new_data_len = 0
        bookmark_start = []
        bookmark_end = []
        output = ""
        match = re.finditer(keyword, data)
        for m in match:
            new_data.extend(data_list_all[offset + prev_pos:offset + m.start()])
            new_data.extend(replacement_data)
            prev_pos = m.end()
            new_data_prev_len = new_data_len
            new_data_len += m.start() - prev_pos + replacement_len

            if is_printable(m.group()):
                output += "Offset: 0x%x Search hit: %s\n" % (offset + m.start(), re.sub("[\r\n\v\f]", "", m.group()))
            else:
                output += "Offset: 0x%x Search hit: %s (hex)\n" % (offset + m.start(), binascii.hexlify(m.group()))

            if num_hits > 0 and offset + new_data_prev_len + m.start() == bookmark_end[-1]:
                bookmark_end[-1] = offset + new_data_prev_len + m.start() + replacement_len
            else:
                bookmark_start.append(offset + new_data_prev_len + m.start())
                bookmark_end.append(offset + new_data_prev_len + m.start() + replacement_len)

            num_hits += 1

        if output != "":
            print(output)

        print("Elapsed time (replace): %f (sec)" % (time.time() - time_start))
        time_start = time.time()

        if num_hits > 0:
            if offset + m.end() < data_all_len - 1:
                new_data.extend(data_list_all[offset + m.end():])

            fi.newDocument("New file", 1)
            fi.setDocument("".join(new_data))

        if num_hits > 100 and not bookmark_yesno_dialog(num_hits):
            do_bookmark = False
        else:
            do_bookmark = True

        if do_bookmark:
            for i in range(0, len(bookmark_start)):
                fi.setBookmark(bookmark_start[i], bookmark_end[i] - bookmark_start[i], hex(bookmark_start[i]), "#aaffaa")

            if num_hits == 1:
                print("Added a bookmark to the search hit.")
            elif num_hits > 1:
                print("Added bookmarks to the search hits.")

            print("Elapsed time (bookmark): %f (sec)" % (time.time() - time_start))

def yara_scan(fi):
    """
    Scan selected region (the whole file if not selected) with YARA
    """
    cp = ctypes.windll.kernel32.GetACP()
    cp = "cp%d" % cp

    num_file = fi.getDocumentCount()
    if num_file < 2:
        if num_file == 1:
            print("Please open a file to be scanned and a YARA rule file before using YARA scan plugin.")

        return

    file_list = ""
    for i in range(num_file):
        fi.activateDocumentAt(i)
        file_list += "%s\r\n" % fi.getDocumentName().decode(cp).encode("utf-8")

    # Do not show command prompt window
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute file_comparison_dialog.py to show GUI
    # GUI portion is moved to send_to.py to avoid hangup of FileInsight
    p = subprocess.Popen(["py.exe", "-3", "Search/yara_scan_dialog.py"], startupinfo=startupinfo, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    stdout_data, stderr_data = p.communicate(input=file_list)
    ret = p.wait()

    if ret == -1:
        print("yara-python is not installed.")
        print("Please install it with 'py.exe -3 -m pip install yara-python' and try again.")
        return

    if stdout_data == "":
        return
    (scanned_file_index, rule_file_index) = stdout_data.split()

    time_start = time.time()

    fi.activateDocumentAt(int(scanned_file_index))
    length_sel = fi.getSelectionLength()
    offset = fi.getSelectionOffset()
    if length_sel > 0:
        data = fi.getSelection()
        data_len = length_sel
    else:
        data = fi.getDocument()
        data_len = fi.getLength()
        offset = 0

    if data == "":
        return

    fi.activateDocumentAt(int(rule_file_index))
    rule = fi.getDocument()

    # Create a temporary file for scanned file
    fd, scanned_filepath = tempfile.mkstemp()
    handle = os.fdopen(fd, "wb")
    handle.write(data)
    handle.close()

    # Create a temporary file for YARA rule file
    fd, rule_filepath = tempfile.mkstemp()
    handle = os.fdopen(fd, "wb")
    handle.write(rule)
    handle.close()

    # Do not show command prompt window
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute binwalk_scan.py for scanning with binwalk
    p = subprocess.Popen(["py.exe", "-3", "Search/yara_scan.py", scanned_filepath, rule_filepath, str(offset)], startupinfo=startupinfo, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Receive scan result
    stdout_data, stderr_data = p.communicate()
    ret = p.wait()

    # Cleanup
    os.remove(scanned_filepath)
    os.remove(rule_filepath)

    if ret == -1:
        print("yara-python is not installed.")
        print("Please install it with 'py.exe -3 -m pip install yara-python' and try again.")
        return

    if ret == -2: # Exception caught
        print(stdout_data)
        return

    if length_sel > 0:
        print("Scanned from offset %s to %s." % (hex(offset), hex(offset + data_len - 1)))
    else:
        print("Scanned the whole file.")

    print(stdout_data),

    if ret == 0:
        print("No YARA rule matched.")
        print("Elapsed time (scan): %f (sec)" % (time.time() - time_start))
        return

    print("Elapsed time (scan): %f (sec)" % (time.time() - time_start))
    time_start = time.time()

    num_hits = 0
    prev_string = ""
    bookmark_start = []
    bookmark_end = []
    for l in stdout_data.splitlines():
        offset_matched = int(l.split()[1], 0)
        size_matched = int(l.split()[3], 0)
        m = re.match("^Offset: (.+) size: (.+) rule: (.+) tag: (.*) identifier: (.+) matched: (.+)$", l)
        identifier_matched = m.groups()[4]
        if num_hits > 0 and identifier_matched == prev_string and offset_matched <= bookmark_end[-1]:
            bookmark_end[-1] = offset_matched + size_matched
        else:
            bookmark_start.append(offset_matched)
            bookmark_end.append(offset_matched + size_matched)
        prev_string = identifier_matched
        num_hits += 1

    if len(bookmark_start) > 100 and not bookmark_yesno_dialog(len(bookmark_start)):
        do_bookmark = False
    else:
        do_bookmark = True

    if do_bookmark:
        fi.activateDocumentAt(int(scanned_file_index))
        for i in range(0, len(bookmark_start)):
            fi.setBookmark(bookmark_start[i], bookmark_end[i] - bookmark_start[i], hex(bookmark_start[i]), "#aaffaa")

        if num_hits == 1:
            print("Added a bookmark to the search hit.")
        elif num_hits > 1:
            print("Added bookmarks to the search hits.")

        print("Elapsed time (bookmark): %f (sec)" % (time.time() - time_start))
