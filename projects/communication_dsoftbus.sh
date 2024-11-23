# Elixir definitions for communication_dsoftbus

version_dir()
{
    grep "^OpenHarmony" |
    sed -re 's/^OpenHarmony-/v/'
}

version_rev()
{
    grep "^v" |
    sed -re 's/^v/OpenHarmony-/'
}

# get_tags()
# {
#     git tag |
#     grep 'OpenHarmony'
# }

# list_tags_h()
# {
#     echo "$tags" |
#     tac |
#     # sed -r 's/^OpenHarmony-v?/v/' |
#     # sed -r 's/-Release$//' |
#     # sed -r 's/^OpenHarmony-([0-9]+)\.([0-9]+)(.*)$/\1 \1.\2 OpenHarmony-\1.\2\3/'
#     sed -r 's/^(v[0-9]+)\.([0-9]+)(.*)$/\1 \1.\2 \1.\2\3/'
# }
