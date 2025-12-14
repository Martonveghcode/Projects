/** Adds a custom menu on file open */
function onOpen() {
  SlidesApp.getUi()
    .createMenu('Style Tools')
    .addItem('Apply Text Style…', 'showSidebar')
    .addToUi();
}

/** Opens the sidebar UI */
function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('Apply Text Style');
  SlidesApp.getUi().showSidebar(html);
}

/** Entry point called from the sidebar */
function applyTextStyle(options) {
  const { fontFamily, weight, removeHighlight } = options || {};
  if (!fontFamily) throw new Error('Font family is required.');

  const setBold = String(weight || 'Normal').toLowerCase() === 'bold';

  const pres = SlidesApp.getActivePresentation();
  const slides = pres.getSlides();

  let boxes = 0;

  slides.forEach(slide => {
    slide.getPageElements().forEach(el => processElement_(el));
  });

  return { processed: boxes };

  /** Recursively process shapes, groups, and tables */
  function processElement_(el) {
    const type = el.getPageElementType();

    if (type === SlidesApp.PageElementType.GROUP) {
      el.asGroup().getChildren().forEach(child => processElement_(child));
      return;
    }

    if (type === SlidesApp.PageElementType.SHAPE) {
      const shape = el.asShape();
      const textRange = shape.getText();
      if (textRange && textRange.asString().trim() !== '') {
        const style = textRange.getTextStyle();
        style.setFontFamily(fontFamily);
        style.setBold(setBold);
        if (removeHighlight) style.setBackgroundColorTransparent();
        boxes++;
      }
      return;
    }

    if (type === SlidesApp.PageElementType.TABLE) {
      const table = el.asTable();
      for (let r = 0; r < table.getNumRows(); r++) {
        for (let c = 0; c < table.getRow(r).getNumCells(); c++) {
          const cell = table.getCell(r, c);
          const tr = cell.getText();
          if (tr && tr.asString().trim() !== '') {
            const st = tr.getTextStyle();
            st.setFontFamily(fontFamily);
            st.setBold(setBold);
            if (removeHighlight) st.setBackgroundColorTransparent();
            boxes++;
          }
        }
      }
      return;
    }

    // other element types (images, lines, etc.) are ignored
  }
}
