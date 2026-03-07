"""Shared fixtures for the Formulation-Generator test suite."""

import pytest


@pytest.fixture
def sample_request():
    """A typical user request payload."""
    return {
        "odor_type": "Diesel",
        "family_type": "Herbal",
        "tags": "pine, herbal, glue, peppery",
        "odor_description": "strong earthy diesel smell",
        "intensity_1_10": 7,
        "cannabis_forward": 5,
        "fruity_forward": 2,
        "dessert_forward": 0,
    }


@pytest.fixture
def sample_row():
    """A formulation row as it would come from the DB."""
    return {
        "name": "OG Kush Blend",
        "product_code": "OGK-001",
        "odor_type": "Diesel",
        "family_type": "Herbal",
        "tags": "pine, herbal, earthy",
        "odor_description": "strong diesel and earthy notes",
        "intensity_1_10": 7,
        "cannabis_forward": 6,
        "fruity_forward": 1,
        "dessert_forward": 0,
        "aroma_color": "#4a7c3f",
        "notes_color_secondary": "#2e5c2a",
        "main_terpenes": "Myrcene, Caryophyllene",
    }


@pytest.fixture
def sample_rows():
    """Multiple formulation rows for testing recommendation sorting."""
    return [
        {
            "name": "Perfect Match",
            "odor_type": "Diesel",
            "family_type": "Herbal",
            "tags": "pine, herbal, glue, peppery",
            "odor_description": "strong earthy diesel smell",
            "intensity_1_10": 7,
            "cannabis_forward": 5,
            "fruity_forward": 2,
            "dessert_forward": 0,
            "aroma_color": "#4a7c3f",
        },
        {
            "name": "Partial Match",
            "odor_type": "Diesel",
            "family_type": "Fruity",
            "tags": "citrus, sweet",
            "odor_description": "bright citrus notes",
            "intensity_1_10": 3,
            "cannabis_forward": 0,
            "fruity_forward": 8,
            "dessert_forward": 5,
            "aroma_color": "#ffa500",
        },
        {
            "name": "No Match",
            "odor_type": "Floral",
            "family_type": "Sweet",
            "tags": "rose, lavender",
            "odor_description": "delicate floral bouquet",
            "intensity_1_10": 2,
            "cannabis_forward": 0,
            "fruity_forward": 0,
            "dessert_forward": 9,
            "aroma_color": "#ff69b4",
        },
    ]
