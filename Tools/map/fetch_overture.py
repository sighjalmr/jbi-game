import pyarrow.fs as fs, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc, os, sys, json
from concurrent.futures import ThreadPoolExecutor
REL='overturemaps-us-west-2/release/2026-10-21.0'
X0,Y0,X1,Y1=60.650,56.810,60.715,56.852
s3=fs.S3FileSystem(anonymous=True, region='us-west-2', proxy_options=os.environ['HTTPS_PROXY'])
out=sys.argv[1]
def rg_hits(path):
    try:
        md=pq.ParquetFile(path, filesystem=s3).metadata
    except Exception as e:
        return path,[]
    names=[md.schema.column(i).path for i in range(md.num_columns)]
    idx={n:i for i,n in enumerate(names)}
    hits=[]
    for r in range(md.num_row_groups):
        g=md.row_group(r)
        try:
            xmin=g.column(idx['bbox.xmin']).statistics.min; xmax=g.column(idx['bbox.xmax']).statistics.max
            ymin=g.column(idx['bbox.ymin']).statistics.min; ymax=g.column(idx['bbox.ymax']).statistics.max
        except Exception: hits.append(r); continue
        if xmax>=X0 and xmin<=X1 and ymax>=Y0 and ymin<=Y1: hits.append(r)
    return path,hits
for theme,typ in [('buildings','building'),('transportation','segment'),('base','land_use'),('base','water'),('base','land'),('base','land_cover'),('base','infrastructure'),('places','place'),('buildings','building_part')]:
    d=f'{REL}/theme={theme}/type={typ}/'
    files=[f.path for f in s3.get_file_info(fs.FileSelector(d)) if f.path.endswith('.parquet')]
    with ThreadPoolExecutor(32) as ex: res=list(ex.map(rg_hits, files))
    tabs=[]
    for path,hits in res:
        if not hits: continue
        f=pq.ParquetFile(path, filesystem=s3)
        t=f.read_row_groups(hits)
        b=t.column('bbox')
        m=pc.and_(pc.and_(pc.greater_equal(pc.struct_field(b,'xmax'),X0),pc.less_equal(pc.struct_field(b,'xmin'),X1)),
                  pc.and_(pc.greater_equal(pc.struct_field(b,'ymax'),Y0),pc.less_equal(pc.struct_field(b,'ymin'),Y1)))
        t=t.filter(m)
        if t.num_rows: tabs.append(t)
    n=sum(t.num_rows for t in tabs)
    print(theme,typ,len(files),'files ->',n,'rows',flush=True)
    if tabs:
        pq.write_table(pa.concat_tables(tabs,promote_options='permissive'), f'{out}/{theme}_{typ}.parquet')
