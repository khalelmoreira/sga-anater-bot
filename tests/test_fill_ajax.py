"""
Offline check that the repeatable "Adicionar" panels wait for the site's AJAX
response before filling the next row. Mock page: Adicionar shows the
"Aguardando..." overlay, and only 800 ms later commits the row and clears
Descrição/Quantidade (Unidade Medida keeps its value, like the real site).
A fixed 300 ms sleep fills the next row too early and loses it. Run with:

    python -m tests.test_fill_ajax
"""

from playwright.sync_api import sync_playwright

from src.fill.locators import select_is_already_set
from src.fill.site import fill_repeatable_panel, group_by_panel_index
from src.schema.model import CanonicalField

PAGE = """
<form id="formularioUpf"><div id="sgaAjaxLoading" style="display:none">Aguardando...</div>
<span id="formularioUpf:idPanelPatrimonio">
  <table id="rows"></table>
  <select id="formularioUpf:idUpfPatrimonioAd"><option value="" selected>--Selecione--</option>
    <option>01-A</option><option>02-B</option><option>03-C</option></select>
  <input id="formularioUpf:idUpfPatrimonioQuantidadeAd">
  <select id="formularioUpf:idUpfPatrimonioUnidMedidaAd"><option value="" selected>--Selecione--</option>
    <option>unidade</option><option>unidade animal</option></select>
  <a href="#" onclick="add(); return false; /* idPanelPatrimonio */">Adicionar</a>
</span></form>
<script>
function add() {
  const ov = document.getElementById('sgaAjaxLoading');
  ov.style.display = 'block';
  setTimeout(() => {
    const d = document.getElementById('formularioUpf:idUpfPatrimonioAd');
    const q = document.getElementById('formularioUpf:idUpfPatrimonioQuantidadeAd');
    const u = document.getElementById('formularioUpf:idUpfPatrimonioUnidMedidaAd');
    if (d.value && q.value && u.value) {
      document.getElementById('rows').insertAdjacentHTML('beforeend',
        '<tr><td>' + d.value + '</td><td>' + q.value + '</td><td>' + u.value + '</td></tr>');
    }
    d.value = ''; q.value = '';
    ov.style.display = 'none';
  }, 800);
}
</script>
"""


def _row(idx, descricao, quantidade, unidade):
    p = f"patrimonio[{idx}]"
    return [
        CanonicalField(p, "Descrição", "idUpfPatrimonioAd", descricao, "high", field_type="select"),
        CanonicalField(p, "Quantidade", "idUpfPatrimonioQuantidadeAd", quantidade, "high"),
        CanonicalField(p, "Unidade Medida", "idUpfPatrimonioUnidMedidaAd", unidade, "high", origin="fixed", field_type="select"),
    ]


def test_rows_survive_slow_ajax(page):
    page.set_content(PAGE)
    fields = _row(0, "01-A", "2", "unidade") + _row(1, "02-B", "3", "unidade") + _row(2, "03-C", "5", "unidade animal")
    fill_repeatable_panel(page, "patrimonio", group_by_panel_index(fields))
    rows = page.eval_on_selector_all("#rows tr", "trs => trs.map(tr => [...tr.children].map(td => td.textContent))")
    assert rows == [["01-A", "2", "unidade"], ["02-B", "3", "unidade"], ["03-C", "5", "unidade animal"]], rows


def test_already_set_is_not_a_prefix_match(page):
    page.set_content(PAGE)
    page.select_option("#formularioUpf\\:idUpfPatrimonioUnidMedidaAd", "unidade")
    assert select_is_already_set(page, "idUpfPatrimonioUnidMedidaAd", "unidade")
    assert not select_is_already_set(page, "idUpfPatrimonioUnidMedidaAd", "unidade animal")


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for test in (test_rows_survive_slow_ajax, test_already_set_is_not_a_prefix_match):
            test(browser.new_page())
        browser.close()
    print("ok")
