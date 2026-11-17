import argparse,json,sys
from .core import build,verify,Invalid

def main():
    parser=argparse.ArgumentParser(description='Compare explicitly declared proportion definitions and grouped counts locally.')
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compare');c.add_argument('contract');c.add_argument('before');c.add_argument('after');c.add_argument('--out',required=True)
    v=sub.add_parser('verify');v.add_argument('bundle')
    args=parser.parse_args()
    try:
        if args.command=='verify':result=verify(args.bundle)
        else:
            report=build(args.contract,args.before,args.after,args.out)
            result={'written':args.out,'comparison_ready':report['comparison_ready'],'reasons':report['reasons']}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (Invalid,OSError,ValueError,TypeError,OverflowError):
        print('Error: input, output or bundle failed validation. No private values are echoed.',file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
