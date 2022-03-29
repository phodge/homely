# Creating a section

You can define a section like this:

    @section
    def some_section():
        print("Do some things")


You can make a section optional like this:

    @section(optional=True)
    def some_section():
        print("Do some things")

The first time homely encounters an optional @section it will ask you whether you want to run it.
Your choice will be remembered for next time. You can modify your choice later by running `homely
update --alwaysprompt`.


You can tell homely to only run a given section once very N days using the `interval` parametery:

    @section(interval='14d')
    def vim_plug_update():
        execute(['vim', '+PlugUpdate'])
