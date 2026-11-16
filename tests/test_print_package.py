import json
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from kdp.book_config import BookConfig
from kdp.project import BookProject
from kdp.print_package import export_package


def fixture_book(tmp_path):
    md, config = BookProject('Prueba impresión','Autor',[(f'Nombre {i}',f'an animal {i}') for i in range(11)],BookConfig()).save_new(tmp_path)
    root = md.parent/'output'/'Prueba impresión'
    (root/'pages_clean').mkdir(parents=True)
    (root/'cover').mkdir(); (root/'interior').mkdir()
    from kdp.parser import parse_book
    pages = {}
    for idea in parse_book(md).page_ideas:
        Image.new('L',(10,10),255).save(root/'pages_clean'/idea.filename)
        pages[f'{idea.number:02d}'] = {'status':'ok','visual_reviewed':True}
    (root/'manifest.json').write_text(json.dumps({'pages':pages}))
    with pikepdf.Pdf.new() as pdf:
        for _ in range(24):pdf.add_blank_page(page_size=(612,792))
        pdf.save(root/'interior'/'Prueba impresión_interior.pdf')
    for name,color in [('front','blue'),('back','red')]:
        Image.new('RGB',(400,600),color).save(root/'cover'/f'{name}.png')
    return md,config,root


def test_exports_exact_dimensions_and_only_deliverables(tmp_path):
    md,config,root = fixture_book(tmp_path)
    out = export_package(md,config,spine=.06,cover_width=17.31,cover_height=11.25,destination=tmp_path/'package')
    with pikepdf.open(out/'cover.pdf') as pdf:
        assert len(pdf.pages)==1
        box=[float(x) for x in pdf.pages[0].MediaBox]
        assert box[2] == pytest.approx(17.31*72,abs=.001)
        assert box[3] == pytest.approx(11.25*72,abs=.001)
    assert set(p.name for p in out.iterdir()) == {'cover.pdf','cover.png','interior.pdf','report.json','LEEME.txt'}
    report=json.loads((out/'report.json').read_text())
    assert report['pages']==24 and report['warnings']
    with pytest.raises(FileExistsError):
        export_package(md,config,spine=.06,cover_width=17.31,cover_height=11.25,destination=out)


def test_blocks_unreviewed_pages_and_wrong_dimensions(tmp_path):
    md,config,root = fixture_book(tmp_path)
    with pytest.raises(ValueError,match='medidas'):
        export_package(md,config,spine=.06,cover_width=20,cover_height=11.25,destination=tmp_path/'bad')
    manifest=json.loads((root/'manifest.json').read_text());manifest['pages']['01']['visual_reviewed']=False
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='revisión visual'):
        export_package(md,config,spine=.06,cover_width=17.31,cover_height=11.25,destination=tmp_path/'bad')
    assert not (tmp_path/'bad').exists()
