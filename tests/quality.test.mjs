/** Regressões das falhas enviadas pelo usuário, verificadas no pacote exportado. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { build } from '../src/generate.mjs';
import { prepareQuality } from '../src/quality.mjs';

const catalog = JSON.parse(fs.readFileSync(new URL('../data/catalog.json', import.meta.url)));

test('quality prefers standard size, shrinks tables to fit and enforces bounds', () => {
  assert.throws(() => prepareQuality({selection:[10],quality:{type:{body:{size:17}}}},catalog), /Escala inválida/);
  const fitted = prepareQuality({selection:[10],quality:{type:{dense:{size:12}}}},catalog).additions[10].find(e=>e.id==='agenda');
  assert(fitted.style.fontSize >= 10 && fitted.style.fontSize < 12);
  assert.throws(() => prepareQuality({selection:[10],quality:{type:{dense:{min:12,size:12}}}},catalog), /Tabela agenda/);
  assert.throws(() => prepareQuality({selection:[10],quality:{fontFit:{step:0.001}}},catalog), /fontFit.step/);
  assert.throws(() => prepareQuality({quality:{hierarchy:{sizes:{title:0}}}},catalog), /Token tipográfico/);
  assert.throws(() => prepareQuality({quality:{hierarchy:{roles:{'65.e2':'unknown'}}}},catalog), /Nível tipográfico/);
  const standard = prepareQuality({selection:[65],quality:{}},catalog);
  const headings = standard.additions[65].filter(e=>e.id.startsWith('card-title-'));
  assert(headings.every(e=>e.style.fontSize===12));
  const configured = prepareQuality({selection:[65],quality:{hierarchy:{sizes:{component:11.5}}}},catalog);
  assert(configured.additions[65].filter(e=>e.id.startsWith('card-title-')).every(e=>e.style.fontSize===11.5));
  assert.throws(() => prepareQuality({selection:[31],quality:{elements:{'31.notes-left':{style:{fontSize:30}}}}},catalog), /fora dos limites/);
});

test('quality preserves narrative across continuation, fits agenda, and embeds native chart workbooks', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(),'quality-regression-'));
  try {
    const result = await build({selection:[1,4,5,10,22,24,27,28,29,31,34,35,38,40,43,45,47,48,51,52,57,58,63,64,65,67,70,71], quality:{},showHidden:true},
      {output:path.join(directory,'reviewed.pptx')});
    assert.equal(result.report.counts.outputSlides,29);
    assert.equal(result.report.slides.length,29);
    assert.deepEqual(result.report.quality.estimatedOverflow,[]);
    const measures = result.report.quality.measurements;
    for (const [slide,id,size] of [[1,'e2',60],[1,'e3',16],[1,'e4',14],[4,'e2',66],[4,'e3',28],[63,'e2',66],[63,'e3',28]]) {
      const coverText = measures.find(e=>e.slide===slide && e.id===id);
      assert.equal(coverText.resolvedFontSize,size);
      assert.deepEqual(coverText.fontSizes,[size]);
      assert.equal(coverText.referenceLocked,true);
    }
    const longCover = measures.find(e=>e.slide===63 && e.id==='e2');
    assert(longCover.box.h>catalog.slides[62].elements.find(e=>e.id==='e2').box.h);
    assert(longCover.box.y+longCover.box.h<=6.66);
    const title = measures.find(e=>e.slide===65 && e.id==='e2');
    assert.equal(title.referenceLocked,true);
    assert.equal(title.resolvedFontSize,22);
    assert.deepEqual(title.fontSizes,[22]);
    const heading = measures.find(e=>e.slide===31 && e.name==='custom.section-0');
    assert.equal(heading.resolvedFontSize,11);
    assert.equal(heading.referenceLocked,true);
    const chartHeading = measures.find(e=>e.slide===31 && e.name==='custom.chart-title-0');
    assert.equal(chartHeading.resolvedFontSize,10);
    for (const item of measures.filter(e=>e.typographyRole==='title')) {
      assert.equal(item.resolvedFontSize,22);
      assert.deepEqual(item.fontSizes,[22]);
    }
    for (const item of measures.filter(e=>e.typographyRole==='tableHeader'))
      if (item.fontSizes.some(size=>size>1)) assert.deepEqual(item.fontSizes,[10]);
    const cards = measures.filter(e=>e.name?.startsWith('custom.card-title-'));
    assert(cards.length>0);
    assert(cards.every(e=>e.resolvedFontSize===12 && e.typographyRole==='component'));
    assert.equal(result.report.quality.continuations.length,1);
    const icons = result.report.quality.layoutConstraints['58'].tableIcons['custom.tactics'];
    assert.equal(icons.length,8);
    for (const icon of icons) {
      assert(Math.abs(icon.textStart-(icon.box.x+icon.box.w)-0.12)<0.0001);
      assert.equal(icon.box.w,0.32);
    }
    const tacticSlide = result.report.slides.find(s=>s.sourceNumber===58);
    assert.equal(tacticSlide.elements.filter(e=>e.name?.match(/^custom\.tactic-icon-\d+-bg$/)).length,8);
    const priorities = result.report.slides.find(s=>s.sourceNumber===51);
    const cardSettings = JSON.parse(fs.readFileSync(new URL('../config.quality.json',import.meta.url))).quality.flow.cards['51'];
    for (const card of cardSettings.cards) {
      const element = id=>priorities.elements.find(e=>e.id===id);
      const background = element(card.title).box;
      const body = element(card.body).box;
      const badge = element(card.badge).box;
      assert(Math.abs(body.x-background.x-0.12)<0.00001);
      assert(Math.abs(background.x+background.w-body.x-body.w-0.12)<0.00001);
      assert(Math.abs(badge.x-background.x-0.12)<0.00001);
      let previous;
      for (const id of card.owners) {
        const owner = element(id).box;
        assert(Math.abs(owner.x-background.x-0.12)<0.00001);
        if (previous) assert(Math.abs(owner.y-previous.y-previous.h-0.04)<0.00001);
        else assert(owner.y>=body.y+body.h+0.0399);
        previous = owner;
        assert.equal(element(id).text,catalog.slides[50].elements.find(e=>e.id===id).text);
      }
      assert(Math.abs(background.y+background.h-previous.y-previous.h-0.12)<0.00001);
    }
    for (const slideNumber of [24,28]) {
      const paddingPlan = result.report.quality.layoutConstraints[String(slideNumber)];
      const padded = paddingPlan.adjustments.filter(a=>a.constraint==='native-container-padding');
      assert(padded.length>0);
      for (const item of padded) assert([0.06,0.12].includes(item.padding));
    }
    const timelineBody = measures.find(e=>e.slide===24 && e.id==='e14');
    assert.deepEqual(timelineBody.fontSizes,[10,11]);
    const participant = measures.find(e=>e.slide===28 && e.id==='e52');
    assert.deepEqual(participant.fontSizes,[10,12]);
    const reviewed = result.report.quality.layoutConstraints;
    for (const [number,ids] of [[47,['e15','e16','e17','e18']],[70,['e2','e4']]]) {
      const output = result.report.slides.find(s=>s.sourceNumber===number);
      for (const id of ids) {
        const original = catalog.slides[number-1].elements.find(e=>e.id===id).text;
        const actual = output.elements.find(e=>e.id===id).text;
        assert.equal(actual.replace(/\s+/g,' ').trim(),original.replace(/\s+/g,' ').trim());
      }
    }

    const callouts = reviewed['35'].adjustments.filter(a=>a.constraint==='bounded-callout');
    assert.equal(callouts.length,5);
    for (const item of callouts) {
      const text = measures.find(m=>m.slide===35 && m.id===item.id);
      assert(text.box.y>=item.container.y+0.1199);
      assert(text.box.y+text.box.h<=item.container.y+item.container.h-0.1199);
      assert(text.requiredHeight<=text.availableHeight+0.005);
    }
    const bands = reviewed['43'].adjustments.filter(a=>a.constraint==='content-sized-band');
    assert.equal(bands.length,2);
    assert(bands[1].box.w<1.1);
    assert(Math.abs(bands[0].box.x+bands[0].box.w-bands[1].box.x)<0.00001);
    assert(reviewed['70'].notes.includes('e6'));
    const riskNote = measures.find(m=>m.slide===70 && m.id==='e6');
    assert.equal(riskNote.resolvedFontSize,8);
    assert(riskNote.box.y>=reviewed['70'].contentBottom+0.1399);
    assert(reviewed['48'].verticalTableLabels.e6.some(e=>e.text==='Tailwinds'));
    assert(reviewed['57'].verticalTableLabels.e18.some(e=>e.text==='Loans'));
    assert(reviewed['57'].tableOverlays.e18.length>0);
    const legends = reviewed['57'].adjustments.filter(a=>a.constraint==='legend-clearance');
    for (const legend of legends) assert(Math.abs(legend.box.x-legend.marker.x-legend.marker.w-0.08)<0.00001);
    assert(result.report.quality.workbookRepairs.some(r=>r.repair==='cached-xlsx-replaces-xlsb'));
    assert(result.report.quality.workbookRepairs.some(r=>r.repair==='valid-table-range'));
    const journey = result.report.slides.find(s=>s.sourceNumber===64);
    const journeyPlan = result.report.quality.layoutConstraints['64'];
    const journeyCards = journeyPlan.adjustments.filter(a=>a.constraint==='icon-before-card-text');
    assert.equal(journeyCards.length,2);
    for (const card of journeyCards) {
      const title = journey.elements.find(e=>e.id===card.heading);
      const body = journey.elements.find(e=>e.id===card.id);
      assert(Math.abs(title.box.x-card.box.x-0.12)<0.00001);
      assert(Math.abs(card.box.x+card.box.w-title.box.x-title.box.w-0.12)<0.00001);
      assert(body.box.y>=title.box.y+title.box.h+0.0599);
      assert(body.box.y+body.box.h<=card.box.y+card.box.h-0.1199);
      const original = catalog.slides[63].elements.find(e=>e.id===card.id).text;
      assert.equal((title.text+' '+body.text).replace(/\s+/g,' ').trim(),original.replace(/\s+/g,' ').trim());
    }
    const economics = result.report.slides.find(s=>s.sourceNumber===71);
    const economicPlan = result.report.quality.layoutConstraints['71'];
    const economicCards = economicPlan.adjustments.filter(a=>a.constraint==='icon-before-card-text');
    assert.equal(economicCards.length,4);
    const firstBodyY = economicCards[0].bodyBox.y;
    for (const card of economicCards) {
      const element = id=>economics.elements.find(e=>e.id===id);
      const heading = element(card.heading);
      const body = element(card.id);
      assert(Math.abs(body.box.y-firstBodyY)<0.00001);
      assert(Math.abs(heading.box.x-card.box.x-0.12)<0.00001);
      assert(heading.box.x+heading.box.w<=card.box.x+card.box.w-0.1199);
      assert(body.box.y>=heading.box.y+heading.box.h+0.1199);
      assert(body.box.y+body.box.h<=card.box.y+card.box.h-0.1199);
      const original = catalog.slides[70].elements.find(e=>e.id===card.id).text;
      assert.equal((heading.text+' '+body.text).replace(/\s+/g,' ').trim(),original.replace(/\s+/g,' ').trim());
    }
    const panelSlide = result.report.slides.find(s=>s.sourceNumber===52);
    for (const [background,header,body] of [['e30','e228','e13'],['e50','e227','e51'],['e60','e138','e64'],['e62','e139','e71'],['e63','e137','e75']]) {
      const bg = panelSlide.elements.find(e=>e.id===background).box;
      const title = panelSlide.elements.find(e=>e.id===header).box;
      const content = panelSlide.elements.find(e=>e.id===body);
      assert(Math.abs(title.x-bg.x-0.12)<0.00001);
      assert(Math.abs(bg.x+bg.w-content.box.x-content.box.w-0.12)<0.00001);
      assert(Math.abs(bg.y+bg.h-content.box.y-content.box.h-0.12)<0.00001);
      const original = catalog.slides[51].elements.find(e=>e.id===body).text;
      assert.equal(content.text,original);
    }
    for (const [marker,body] of [['e243','e13'],['e244','e13'],['e66','e51'],['e69','e64'],['e20','e71'],['e72','e75']]) {
      const dot = panelSlide.elements.find(e=>e.id===marker).box;
      const content = panelSlide.elements.find(e=>e.id===body).box;
      assert(dot.x+dot.w < content.x);
      assert(Math.abs(dot.w-dot.h)<0.00001);
    }
    const footerPlan = result.report.quality.layoutConstraints['38'];
    const benchmark = result.report.slides.find(s=>s.sourceNumber===38).elements.find(e=>e.id==='e9');
    assert(benchmark.box.y+benchmark.box.h <= footerPlan.contentBottom+0.001);
    const band = measures.find(e=>e.slide===38 && e.id==='e14');
    assert.equal(band.typographyRole,'kicker');
    assert.equal(band.resolvedFontSize,10);
    const strategy = result.report.slides.find(s=>s.sourceNumber===45).elements;
    const label = strategy.find(e=>e.id==='e8');
    const annotation = strategy.find(e=>e.id==='e18');
    assert(label.box.x+label.box.w <= annotation.box.x);
    const roadmap = result.report.slides.find(s=>s.sourceNumber===65).elements;
    const appendix = roadmap.find(e=>e.name==='custom.appendix');
    const lastCard = roadmap.find(e=>e.name==='custom.card-2-0');
    assert(appendix.box.y >= lastCard.box.y+lastCard.box.h+0.1);
    const comparison = result.report.slides.find(s=>s.sourceNumber===34).elements;
    const legend = comparison.find(e=>e.name==='custom.legend');
    const matrix = comparison.find(e=>e.kind==='table');
    assert(legend.box.y >= matrix.box.y+matrix.box.h+0.1);


    const agenda = result.report.slides.find(s=>s.sourceNumber===10);
    assert.equal(agenda.elements.filter(e=>e.kind==='table').length,1);
    assert(agenda.elements.find(e=>e.kind==='table').text.includes('Cocktail with clients'));
    assert.equal(result.report.slides.flatMap(s=>s.elements).filter(e=>e.kind==='chart').length,9);
    const check = spawnSync('python3',['-c',`
import sys,zipfile,xml.etree.ElementTree as E,json,posixpath
z=zipfile.ZipFile(sys.argv[1]); ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
for name in z.namelist():
 if '/slideMasters/' in name and name.endswith('.xml'):
  root=E.fromstring(z.read(name))
  for prop in root.findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}titleStyle//a:defRPr',ns):
   assert prop.get('sz')=='2200', 'master must share the title token'
 if name in {'ppt/slides/slide10.xml','ppt/slides/slide29.xml','ppt/slides/slide34.xml','ppt/slides/slide40.xml','ppt/slides/slide58.xml'}:
  root=E.fromstring(z.read(name))
  for body in root.findall('.//a:tbl//a:txBody',ns):
   assert body.find('a:p',ns) is not None, 'blank cells must keep a structural paragraph'
  for cell in root.findall('.//a:tbl//a:tcPr',ns):
   assert cell.get('anchor') != 'mid'
  for pp in root.findall('.//a:tbl//a:pPr',ns):
   if pp.find('a:spcAft',ns) is not None: assert pp.find('a:spcAft/a:spcPts',ns).get('val')=='0'
   if pp.find('a:lnSpc',ns) is not None: assert pp.find('a:lnSpc/a:spcPct',ns).get('val')=='100000'
 if name=='ppt/slides/slide58.xml':
  root=E.fromstring(z.read(name)); frame=root.find('.//p:graphicFrame',ns)
  off=frame.find('p:xfrm/a:off',ns); emu=914400
  tx,ty=int(off.get('x'))/emu,int(off.get('y'))/emu
  table=frame.find('.//a:tbl',ns); cols=[int(c.get('w'))/emu for c in table.findall('a:tblGrid/a:gridCol',ns)]
  rows=table.findall('a:tr',ns); y=ty+int(rows[0].get('h'))/emu
  for index,row in enumerate(rows[1:],1):
   node=next(sp for sp in root.findall('.//p:sp',ns) if sp.find('p:nvSpPr/p:cNvPr',ns).get('name')==f'custom.tactic-icon-{index}-bg')
   xf=node.find('p:spPr/a:xfrm',ns); pos=xf.find('a:off',ns); ext=xf.find('a:ext',ns)
   x,iy,w,h=[int(n)/emu for n in [pos.get('x'),pos.get('y'),ext.get('cx'),ext.get('cy')]]
   height=int(row.get('h'))/emu; cell=row.findall('a:tc',ns)[2]
   text_left=tx+sum(cols[:2])+int(cell.find('a:tcPr',ns).get('marL'))/emu
   assert abs(text_left-(x+w)-0.12)<0.00002, 'icon/text gap must match after export'
   assert abs(iy+h/2-(y+height/2))<0.00002, 'icon must follow final row height'
   y+=height
 if name.startswith('ppt/charts/generated-') and name.endswith('.xml'):
  root=E.fromstring(z.read(name))
  assert root.find('.//c:ser/c:cat',ns) is not None
  rel=posixpath.join(posixpath.dirname(name),'_rels',posixpath.basename(name)+'.rels')
  rr=E.fromstring(z.read(rel))
  workbooks=[r for r in rr if r.get('Type','').endswith('/package')]
  assert workbooks
  for r in workbooks: assert posixpath.normpath(posixpath.join(posixpath.dirname(name),r.get('Target'))) in z.namelist()
print('native workbooks valid')
`,result.outputPath],{encoding:'utf8'});
    assert.equal(check.status,0,check.stderr);
    const pages = result.report.slides.filter(s=>s.sourceNumber===5);
    const original = catalog.slides[4].elements.find(e=>e.id==='e9').text.replace(/\s/g,'');
    const actual = pages.map(p=>p.elements.find(e=>e.id==='e9').text).join('').replace(/\s/g,'');
    assert.equal(actual,original);
  } finally { fs.rmSync(directory,{recursive:true,force:true}); }
});
