"""Validation schemas. Dashboard content can be edited by non-admin editors:
every value injected into the DOM (URLs, colours, icon classes) is strictly
validated to prevent XSS."""
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

_FORBIDDEN_SCHEMES = re.compile(r"^\s*(javascript|vbscript|data|file):", re.I)
_CSS_UNSAFE = re.compile(r"[\"'()\\\s<>;{}]")
_COLOR = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s/deg]+\)|[a-zA-Z]{3,30}|)$"
)
_ICON = re.compile(r"^[a-z0-9 \-]*$")
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _link(v: str) -> str:
    v = (v or "").strip()
    if _FORBIDDEN_SCHEMES.match(v) or any(ord(c) < 32 for c in v):
        raise ValueError("Forbidden URL scheme")
    return v


def _http(v: str) -> str:
    v = (v or "").strip()
    if v and not re.match(r"^https?://[^\s]+$", v, re.I):
        raise ValueError("Status URL must start with http:// or https://")
    return v


def _image(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return v
    if _CSS_UNSAFE.search(v) or not re.match(r"^(https?://|/)", v, re.I) or v.startswith("//"):
        raise ValueError("Invalid image URL (http(s):// or /path, without spaces or quotes)")
    return v


def _color(v: str) -> str:
    v = (v or "").strip()
    if not _COLOR.match(v):
        raise ValueError("Invalid CSS colour")
    return v


def _icon(v: str) -> str:
    v = (v or "").strip()
    if not _ICON.match(v):
        raise ValueError("Invalid icon class")
    return v


def _slug(v: str) -> str:
    if not _SLUG.match(v):
        raise ValueError("Invalid identifier (lowercase letters, digits, dashes)")
    return v


Link = Annotated[str, Field(max_length=2048), AfterValidator(_link)]
Image = Annotated[str, Field(max_length=1024), AfterValidator(_image)]
HttpUrl = Annotated[str, Field(max_length=2048), AfterValidator(_http)]
Color = Annotated[str, Field(max_length=64), AfterValidator(_color)]
Icon = Annotated[str, Field(max_length=128), AfterValidator(_icon)]
Slug = Annotated[str, AfterValidator(_slug)]
Text = Annotated[str, Field(max_length=255)]
LongText = Annotated[str, Field(max_length=4000)]
Target = Literal["_blank", "_self", ""]


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Item(_M):
    id: Text = ""
    name: Text = ""
    subtitle: Text = ""
    url: Link = ""
    icon: Icon = ""
    logo: Image = ""
    tag: Text = ""
    tagstyle: Literal["", "is-info", "is-success", "is-warning", "is-danger", "is-primary"] = ""
    target: Target = "_blank"
    keywords: Text = ""
    background: Color = ""
    # Web application status check (green / orange / red dot on the card)
    status_check: bool = False
    status_url: HttpUrl = ""  # empty = the link URL
    status_ignore_tls: bool = False


class Section(_M):
    id: Text = ""
    name: Text = ""
    icon: Icon = ""
    items: list[Item] = Field(default_factory=list, max_length=300)


class NavLink(_M):
    name: Text = ""
    icon: Icon = ""
    url: Link = ""
    target: Target = "_blank"


class Message(_M):
    enabled: bool = False
    style: Literal["", "is-info", "is-success", "is-warning", "is-danger", "is-dark"] = "is-info"
    title: Text = ""
    icon: Icon = ""
    content: LongText = ""


class Background(_M):
    type: Literal["default", "color", "gradient", "image"] = "default"
    color: Color = ""
    gradient_from: Color = ""
    gradient_to: Color = ""
    gradient_angle: int = Field(135, ge=0, le=360)
    image: Image = ""
    overlay: float = Field(0.0, ge=0, le=0.95)
    blur: int = Field(0, ge=0, le=30)


class ThemeColors(_M):
    highlight_primary: Color = ""
    highlight_secondary: Color = ""
    highlight_hover: Color = ""
    background: Color = ""
    card_background: Color = ""
    text: Color = ""
    text_header: Color = ""
    text_title: Color = ""
    text_subtitle: Color = ""
    link: Color = ""


class Colors(_M):
    light: ThemeColors = Field(default_factory=ThemeColors)
    dark: ThemeColors = Field(default_factory=ThemeColors)


class DashboardConfig(_M):
    columns: Literal["auto", "1", "2", "3", "4", "6", "12"] = "3"
    default_theme: Literal["auto", "light", "dark"] = "auto"
    default_layout: Literal["columns", "list"] = "columns"
    show_header: bool = True
    status_interval: int = Field(60, ge=15, le=3600)
    footer: LongText = ""
    background: Background = Field(default_factory=Background)
    colors: Colors = Field(default_factory=Colors)
    message: Message = Field(default_factory=Message)
    links: list[NavLink] = Field(default_factory=list, max_length=30)
    sections: list[Section] = Field(default_factory=list, max_length=100)


class DashboardContent(_M):
    """What a (non-admin) editor may change."""
    title: Annotated[str, Field(min_length=1, max_length=255)]
    subtitle: Text = ""
    logo: Image = ""
    config: DashboardConfig


class DashboardAdmin(DashboardContent):
    slug: Slug
    visibility: Literal["authenticated", "restricted"] = "restricted"
    position: int = 0


class AccessRule(_M):
    group_id: int | None = None
    user_id: int | None = None
    can_edit: bool = False


class PrincipalRule(_M):
    """A rule seen from a group or a user: which dashboard, which permission."""
    dashboard_id: int
    can_edit: bool = False


class ExternalGroupCreate(_M):
    """LDAP / OIDC group declared before anyone from it signs in."""
    source: Literal["ldap", "oidc"]
    # LDAP: group DN. OIDC: value as sent in the groups claim.
    external_id: Annotated[str, Field(min_length=1, max_length=1024)]
    name: Annotated[str, Field(max_length=255)] = ""
    description: str = ""


class ExternalUserCreate(_M):
    """LDAP / OIDC account declared before its first sign-in."""
    source: Literal["ldap", "oidc"]
    username: Annotated[str, Field(min_length=1, max_length=255)]
    display_name: Annotated[str, Field(max_length=255)] = ""
    email: Annotated[str, Field(max_length=255)] = ""


class LoginRequest(_M):
    username: Annotated[str, Field(min_length=1, max_length=255)]
    password: Annotated[str, Field(min_length=1, max_length=1024)]


class ClickEvent(_M):
    dashboard_id: int | None = None
    label: Text = ""
    url: Annotated[str, Field(max_length=2048)] = ""
    section: Text = ""


class LocalUserCreate(_M):
    username: Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")]
    password: Annotated[str, Field(min_length=12, max_length=1024)]
    display_name: Text = ""
    email: Text = ""
    is_superadmin: bool = False
    group_ids: list[int] = Field(default_factory=list)


class UserUpdate(_M):
    display_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None
    password: Annotated[str, Field(min_length=12, max_length=1024)] | None = None
    local_group_ids: list[int] | None = None


class GroupCreate(_M):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str = ""
    is_admin: bool = False


class GroupUpdate(_M):
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    description: str | None = None
    is_admin: bool | None = None
