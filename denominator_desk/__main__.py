import argparse,json,sys
from . import claims, revisions, amounts
from .core import build,verify,Invalid

def main():
    parser=argparse.ArgumentParser(description='Compare explicitly declared proportion definitions and grouped counts locally.')
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compare');c.add_argument('contract');c.add_argument('before');c.add_argument('after');c.add_argument('--out',required=True)
    v=sub.add_parser('verify');v.add_argument('bundle')
    c=sub.add_parser('claim-check');c.add_argument('contract');c.add_argument('before');c.add_argument('after');c.add_argument('document');c.add_argument('claim');c.add_argument('--out',required=True);c.add_argument('--require-match',action='store_true')
    c=sub.add_parser('claim-verify');c.add_argument('bundle');c.add_argument('--require-match',action='store_true')
    c=sub.add_parser('revision-check');c.add_argument('original');c.add_argument('revised');c.add_argument('--out',required=True)
    c=sub.add_parser('revision-verify');c.add_argument('bundle')
    amount_check = sub.add_parser('amount-check')
    amount_check.add_argument('source')
    amount_check.add_argument('spec')
    amount_check.add_argument('--out', required=True)
    amount_verify = sub.add_parser('amount-verify')
    amount_verify.add_argument('bundle')
    for amount_parser in (amount_check, amount_verify):
        amount_parser.add_argument(
            '--require-compatible',
            action='store_true',
            help='Exit 3 if any declared amount check is incompatible or needs review.',
        )
    args=parser.parse_args()
    try:
        if args.command.startswith('amount-'):
            report=amounts.verify(args.bundle) if args.command=='amount-verify' else amounts.build(args.source,args.spec,args.out)
            statuses = [row['status'] for row in report['checks']]
            print(json.dumps({
                'consistent': True,
                'statuses': statuses,
                'source_truth_verified': False,
                'source_mapping_verified': False,
                'scope': amounts.SCOPE,
            }))
            compatible_statuses = {
                'equal_under_exact_declarations',
                'compatible_with_declared_rounding',
            }
            if args.require_compatible and not all(status in compatible_statuses for status in statuses):
                return 3
            return 0
        if args.command.startswith('revision-'):
            report=revisions.verify(args.bundle) if args.command=='revision-verify' else revisions.build(args.original,args.revised,args.out)
            print(json.dumps({'consistent':True,'changed':report['changed'],'original_status':report['original']['status'],'revised_status':report['revised']['status'],'correction_justified':None,'history_authenticated':False,'scope':revisions.SCOPE}))
            return 0
        if args.command.startswith('claim-'):
            report=claims.verify(args.bundle) if args.command=='claim-verify' else claims.build(args.contract,args.before,args.after,args.document,args.claim,args.out)
            print(json.dumps({'consistent':True,'status':report['status'],'arithmetic_matches':report['arithmetic_matches'],'semantic_mapping_verified':False,'source_truth_verified':False,'scope':claims.SCOPE}))
            return 3 if args.require_match and report['arithmetic_matches'] is not True else 0
        if args.command=='verify':result=verify(args.bundle)
        else:
            report=build(args.contract,args.before,args.after,args.out)
            result={'written':args.out,'comparison_ready':report['comparison_ready'],'reasons':report['reasons']}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (Invalid,OSError,ValueError,TypeError,OverflowError):
        print('Error: input, output or bundle failed validation. No private values are echoed.',file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
