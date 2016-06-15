# Terraform
Single-command dotfile installation.


# Installation

To install `terraform` on a new machine, use the following command:

    curl --create-dirs https://raw.githubusercontent.com/toomuchphp/terraform/master/bin/terraform -o ~/bin/terraform && chmod 755 ~/bin/terraform

# Getting started

1. If you don't yet have a Dotfiles repo, create an empty repo now.
2. Run terraform add https://your/public/repo.git


# Keeping your repos up-to-date

To update your dotfiles using the latest versions from online repos, run:

    terraform update

If you would like your shell to remind you when it is time to update dotfiles, add one of the
following to your ~/.bashrc (or equivalent):

    terraform updatecheck --daily
    terraform updatecheck --weekly
    terraform updatecheck --monthly
