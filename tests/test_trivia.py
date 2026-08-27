from app.trivia import address_trivia, phone_roast


def test_phone_roast_is_deterministic():
    a = phone_roast("+1-415-555-1691")
    b = phone_roast("+1-415-555-1691")
    assert a == b


def test_phone_roast_detects_prime_last_four():
    lines, _ = phone_roast("555-0101")  # 0101 -> 101, prime
    assert any("prime" in line for line in lines)


def test_phone_roast_detects_palindrome():
    lines, _ = phone_roast("555-1221")
    assert any("palindrome" in line for line in lines)


def test_phone_roast_detects_repdigit():
    lines, _ = phone_roast("555-7777")
    assert any("All four digits are 7" in line for line in lines)


def test_phone_roast_detects_1337_and_420():
    lines, _ = phone_roast("555-1337")
    assert any("1337" in line for line in lines)
    lines, _ = phone_roast("555-0420")
    assert any("420" in line for line in lines)


def test_phone_roast_detects_ascending_run():
    lines, _ = phone_roast("555-6789")
    assert any("6789" in line and "ascending" in line for line in lines)


def test_phone_roast_area_code_fact():
    lines, _ = phone_roast("+1-415-555-9999")  # 415 = SF, ends in a repdigit too
    assert any("415" in line for line in lines)


def test_phone_roast_always_returns_a_line_even_with_no_special_properties():
    # A number engineered to trip none of the special checks: not prime, not a
    # palindrome, not a repdigit, no meme substrings, no run of 4+, area code
    # not in the table.
    lines, grade = phone_roast("555-2468")
    assert len(lines) >= 1
    assert grade


def test_phone_roast_blank_number_still_returns_a_line():
    lines, grade = phone_roast(None)
    assert len(lines) == 1
    assert grade == "C"
    lines, grade = phone_roast("")
    assert len(lines) == 1


def test_address_trivia_exact_city_state_match():
    assert "Fender" in address_trivia("Fullerton", "CA", "USA")


def test_address_trivia_falls_back_to_state():
    assert address_trivia(None, "CA", "USA") == (
        "California alone would be among the world's five largest economies if it were its own country."
    )


def test_address_trivia_falls_back_to_country():
    assert "Fortune 500" in address_trivia(None, None, "USA")


def test_address_trivia_generic_fallback_for_unknown_place():
    assert address_trivia("Nowhereville", "ZZ", "Nowhere") == (
        "No trivia on file for that one — but it's now immortalized in a QR code, so there's that."
    )


def test_address_trivia_no_address_at_all():
    assert address_trivia(None, None, None) == "No address on file. Mysterious. We respect it."
