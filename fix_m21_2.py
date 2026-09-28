"""M2.1.2 — non-blocking follow-ups from Claude review."""

from pathlib import Path
import re

# ==========================================================================
# 1. services/products.py — strict stock regex + price limits
# ==========================================================================
p = Path("app/services/products.py")
text = p.read_text(encoding="utf-8")

# Strict stock validation
text = text.replace(
    '''    if not normalized.lstrip("-").isdigit():
        raise ValueError("Miqdor butun son bo\\u2019lishi kerak")''',
    '''    if not re.fullmatch(r"[0-9]+", normalized):
        raise ValueError("Miqdor butun son bo\\u2019lishi kerak")'''
)

# Add max limits
text = text.replace(
    '''    if price < 0:
        raise ValueError("Narx manfiy bo\\u2019lishi mumkin emas")
    return price''',
    '''    if not price.is_finite():
        raise ValueError("Narx noto\\u2019g\\u2019ri formatda")
    if price < 0:
        raise ValueError("Narx manfiy bo\\u2019lishi mumkin emas")
    if price > Decimal("9999999999.99"):
        raise ValueError("Narx juda katta")
    if price.as_tuple().exponent < -2:
        raise ValueError("Narx 2 xonadan ortiq kasr bo\\u2019lishi mumkin emas")
    return price'''
)

text = text.replace(
    '''    stock = int(normalized)
    if stock < 0:
        raise ValueError("Miqdor manfiy bo\\u2019lishi mumkin emas")
    return stock''',
    '''    stock = int(normalized)
    if stock > 2_147_483_647:
        raise ValueError("Miqdor juda katta")
    return stock'''
)

# Add 'import re' at top
if "import re" not in text.split("from __future__")[1][:500]:
    text = text.replace(
        "from decimal import Decimal, InvalidOperation",
        "import re\nfrom decimal import Decimal, InvalidOperation"
    )

p.write_text(text, encoding="utf-8")
print("OK: services/products.py — strict validation")


# ==========================================================================
# 2. handlers/admin.py — gate back_to_main_menu
# ==========================================================================
p = Path("app/handlers/admin.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
    '''@router.message(F.text == "\\U0001F3E0 Bosh menyu")
async def back_to_main_menu(message: Message, state: FSMContext) -> None:''',
    '''@router.message(F.text == "\\U0001F3E0 Bosh menyu")
@admin_only
async def back_to_main_menu(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:'''
)

# Ensure AsyncSession import
if "from sqlalchemy.ext.asyncio import AsyncSession" not in text:
    text = text.replace(
        "from aiogram.types import Message",
        "from aiogram.types import Message\nfrom sqlalchemy.ext.asyncio import AsyncSession"
    )

p.write_text(text, encoding="utf-8")
print("OK: handlers/admin.py — gated Bosh menyu")


# ==========================================================================
# 3. handlers/products.py — remove stale header, module-level import
# ==========================================================================
p = Path("app/handlers/products.py")
text = p.read_text(encoding="utf-8")

# Remove stale "must remain last" header
text = text.replace(
    """# --------------------------------------------------------------------------
# FSM cancel (must remain last in this router)
# --------------------------------------------------------------------------""",
    "# --------------------------------------------------------------------------\n"
    "# FSM cancel — registered BEFORE ProductForm handlers\n"
    "# --------------------------------------------------------------------------"
)

# Module-level escape import
if "from html import escape" not in text.split("\n\n")[0]:
    text = text.replace(
        "from decimal import Decimal\n",
        "from decimal import Decimal\nfrom html import escape\n"
    )

# Remove inline imports
text = text.replace("    from html import escape\n", "")
text = text.replace("    from html import escape as _esc\n", "")
text = text.replace("from html import escape as _esc\n", "")
text = text.replace("_esc(", "escape(")

p.write_text(text, encoding="utf-8")
print("OK: handlers/products.py — clean imports + headers")


# ==========================================================================
# 4. Compile check
# ==========================================================================
print()
print("Compile check:")
for path in [
    Path("app/services/products.py"),
    Path("app/handlers/admin.py"),
    Path("app/handlers/products.py"),
]:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        print(f"OK: {path}")
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {path}: {e}")