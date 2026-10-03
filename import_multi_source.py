import argparse
from openalex import import_openalex

if __name__ == '__main__':
    p=argparse.ArgumentParser(description='UniScout multi-source importer')
    p.add_argument('--source', choices=['openalex'], default='openalex')
    p.add_argument('--pages', type=int, default=None)
    p.add_argument('--per-page', type=int, default=100)
    p.add_argument('--mailto', default=None)
    args=p.parse_args()
    if args.source == 'openalex': import_openalex(args.pages,args.per_page,args.mailto)
