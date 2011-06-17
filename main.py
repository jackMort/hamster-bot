from chomikuj import Chomik

if __name__ == "__main__":
    chomik = Chomik( '<LOGIN>', '<PASSWORD>' )
    if chomik.connect():
        print chomik.copy_directory_tree( 'some-user' )

# vim: fdm=marker ts=4 sw=4 sts=4
