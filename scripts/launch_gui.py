import sys
if len(sys.argv)>1 and sys.argv[1]=="--verify-core":
    import argparse
    from pathlib import Path
    from inferlm.validation import verify
    parser=argparse.ArgumentParser(description="Verify the packaged local inference core.")
    parser.add_argument("--verify-core",type=Path,required=True,metavar="GGUF")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    verify(args.verify_core,args.output)
else:
    from inferlm.app import main
    raise SystemExit(main())


