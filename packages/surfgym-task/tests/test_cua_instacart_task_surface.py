from pathlib import Path


APP_ROOT = (
    Path(__file__).resolve().parents[3]
    / "third_party"
    / "cua-gym-hub"
    / "websites"
    / "instacart_mock"
)


def test_instacart_ui_persists_every_rewarded_setting() -> None:
    """The browser surface must write the same fields as the CUA reward script."""
    context = (APP_ROOT / "src/context/AppContext.jsx").read_text(encoding="utf-8")
    browser = (APP_ROOT / "src/pages/ProductBrowser.jsx").read_text(encoding="utf-8")
    modal = (APP_ROOT / "src/components/ProductModal.jsx").read_text(encoding="utf-8")
    checkout = (APP_ROOT / "src/pages/Checkout.jsx").read_text(encoding="utf-8")
    mock_data = (APP_ROOT / "src/data/mockData.js").read_text(encoding="utf-8")
    vite_config = (APP_ROOT / "vite.config.js").read_text(encoding="utf-8")
    css = (APP_ROOT / "src/index.css").read_text(encoding="utf-8")

    assert "UPDATE_REPLACEMENT" in context
    assert "SET_DELIVERY_SLOT" in context
    assert "SET_DELIVERY_ADDRESS" in context
    assert "replacementPreference" in modal
    assert "state.departments" in browser
    assert "p.departmentId" in browser
    assert "state.deliverySlots" in checkout
    assert "selectedDeliverySlot" in context
    assert "const isUnavailable" in checkout
    assert "disabled={isUnavailable}" in checkout
    assert "departmentId: product.departmentId" in mock_data
    assert "replacementPreference: item.replacementPreference" in mock_data
    assert "tailwindcss" in vite_config
    assert '@import "tailwindcss";' in css
