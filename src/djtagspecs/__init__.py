from __future__ import annotations

import importlib.metadata

from djtagspecs.catalog import TagSpecError
from djtagspecs.catalog import TagSpecFormat
from djtagspecs.catalog import TagSpecLoadError
from djtagspecs.catalog import TagSpecResolutionError
from djtagspecs.catalog import dump_tag_spec
from djtagspecs.catalog import load_tag_spec
from djtagspecs.catalog import merge_tag_specs
from djtagspecs.catalog import validate_tag_spec
from djtagspecs.introspect import TemplateTag
from djtagspecs.introspect import get_installed_templatetags
from djtagspecs.models import EndTag
from djtagspecs.models import IntermediateTag
from djtagspecs.models import Tag
from djtagspecs.models import TagArg
from djtagspecs.models import TagLibrary
from djtagspecs.models import TagSpec

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    # editable install
    __version__ = "0.0.0"

__all__ = [
    "EndTag",
    "IntermediateTag",
    "Tag",
    "TagArg",
    "TagLibrary",
    "TagSpec",
    "TagSpecError",
    "TagSpecFormat",
    "TagSpecLoadError",
    "TagSpecResolutionError",
    "TemplateTag",
    "dump_tag_spec",
    "get_installed_templatetags",
    "load_tag_spec",
    "merge_tag_specs",
    "validate_tag_spec",
]
