import argparse
import json
from pathlib import Path
from assessment_contract import Assessment, validate_materials

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('result',type=Path)
    parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    value=Assessment.model_validate_json(args.result.read_text(encoding='utf-8'))
    if args.input:
        data=json.loads(args.input.read_text(encoding='utf-8'))
        root=args.input.resolve().parent
        materials=[]
        for m in data['materials']:
            path=(root/m['text_file']).resolve()
            if not path.is_relative_to(root): raise ValueError('Material path must remain inside task directory')
            materials.append({**m,'text':path.read_text(encoding='utf-8')})
        validate_materials(value,materials,data.get('confirmed_scope',''))
    print('Valid: '+value.evaluation_status)
