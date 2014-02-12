import sys

if __name__ == "__main__":
    print("""\

WARNING! WARNING! WARNING!

This script has been _deprecated_. All ACL entries are now stored in
config.yml.

You must now specify your ACLs like so:

    networks:
        Foonet:
            acl:
                "foo!bar@baz":
                     - quote
                     - reply

            channels:
                "#foo":
                    acl:
                        "bar!bar@baz":
                            - admin
""")
    sys.exit(1)
