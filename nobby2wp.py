#!/usr/bin/python3

# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Nobby.
#
# Nobby is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# Nobby is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# Nobby. If not, see <http://www.gnu.org/licenses/>.

"""
Upload HTML file to Wordpress host.

Help:          run `nobby2wp.py -h`
Unit tests:    run `py.test` in this directory.
Documentation: https://olitheolix.com/doc/nobby/
Source code:   https://github.com/olitheolix/nobby
"""

import os
import re
import sys
import hashlib
import IPython
import argparse
import tempfile
import subprocess
import collections
import wordpress_xmlrpc as wprpc
import wordpress_xmlrpc.methods as wpmethods

# Convenience data structure to parse the postid file.
Entry = collections.namedtuple('Entry', 'host type ID')

# Convenience.
ipshell = IPython.embed


def updateImageTags(html, wp_path_img):
    """
    Prefix all local image- and href paths in ``html`` with ``wp_path_img``.

    The purpose of this function is to update the local image paths to the ones
    on the Wordpress server. The local image paths created by Nobby are never
    prefixed because all images reside in the same directory as the HTML file.

    :param *str* html: HTML text.
    :param *str* wp_path_img: pdfLaTeX will put its output there.
    :return: **None**
    """
    def repl(m):
        tag_img, img_name = m.groups()
        return tag_img + wp_path_img + img_name

    # Replace the image paths.
    html = re.sub(r'(<img src=")(.*?")', repl, html)

    # Replace the hyperref paths, but only those that start with './'. The
    # author of the LaTeX code is responsible for putting this prefix in. Note
    # that the prefix is irrelevant for images because only Nobby can actually
    # add any images to the HTML file.
    html = re.sub(r'(href=")\./(.*?")', repl, html)
    return html


def updatePost(cred, post_id, post_type, post_title, post_content):
    """
    Set the content of ``post_id`` to ``post_content``.

    Connect to Wordpress with the supplied credentials ``cred`` (see
    :func:`loadCredentials` for more details.)

    Create a new post if ``post_id`` is **None** and return the new
    ID. Otherwise, locate the supplied ``post_id`` and raise an error if
    Wordpress does not know about a post with that ID.

    Set the Wordpress ``post_type``. This is either 'page' or 'post'.  If
    ``post_id`` was not **None**, The ``post_type`` for the ``post_id`` must
    match. Raise an error otherwise.

    The ``post_title`` is mandatory for new posts (ie. ``post_id`` is
    **None**). The old title is recycled for existing posts if ``post_title``
    is **None**.

    The ``post_content`` is the HTML code to publish via Wordpress.

    :param *dict* cred: Wordpress- and SSH credentials dictionary.
    :param *str* post_id: the Wordpress post ID. Use **None** to create new
      post.
    :param *str* post_type: Wordpress post type (usually either 'post' or
      'page')
    :param *str* post_title: The title. Use **None** to keep the old one.
    :param *str* post_content: HTML content of page.
    :return: Wordpress post ID. Same as supplied ``post_id``, unless a new post
      was created (in which case the supplied ``post_id`` was **None**).
    """
    try:
        # Connect to Wordpress host.
        wp_client = wprpc.Client(cred['wp-url'] + '/xmlrpc.php',
                                 cred['wp-user'], cred['wp-pass'])

        # If no post_id was supplied then create a new post/page. Otherwise
        # query Wordpress for the post with that ID.
        if post_id is None:
            # A new post/page always requires a title.
            if post_title is None:
                print('New posts require a title - Abort.')
                sys.exit(1)

            # Instantiate a new Wordpress- post or page.
            if post_type == 'page':
                post = wprpc.WordPressPage()
            else:
                post = wprpc.WordPressPost()

            # Create an empty document in Wordpress and record its ID.
            post.id = wp_client.call(wpmethods.posts.NewPost(post))
            msg = 'Creating new {} on {}\n  Title: {}\n  ID: {}... '
            msg = msg.format(post_type, cred['wp-url'], post_title, post.id)
        else:
            # Retrieve all posts and filter out the one with the correct ID.
            post = wp_client.call(
                wpmethods.posts.GetPosts({'post_type': post_type}))
            post = [_ for _ in post if _.id == post_id]

            # Sanity check: exit immediately if the post ID does not exist.
            if len(post) == 0:
                msg = ('Post ID={} does not exist on host {}. Try deleting'
                       ' ".postid".').format(post_id, cred['wp-url'])
                print(msg)
                sys.exit(1)
            else:
                post = post[0]
            msg = 'Updating existing {} (ID={}) on {}... '
            msg = msg.format(post_type, post_id, cred['wp-url'])

        # Update the post publish it immediately.
        post.post_status = 'publish'
        if post_title is not None:
            post.title = post_title
        post.content = post_content

        print(msg, end='', flush=True)
        ret = wp_client.call(wpmethods.posts.EditPost(post.id, post))
        print('\r' + msg + ' done')
        return post.id
    except wprpc.exceptions.InvalidCredentialsError as e:
        print(e)
        msg = 'Wordpress credentials for host {} are wrong.'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        sys.exit(1)
    except wprpc.exceptions.ServerConnectionError as e:
        print(e)
        msg = 'Cannot connect to host {} with the following credentials'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        sys.exit(1)


def copyImageFiles(cred, path_html, wp_path_img, verbose=False):
    """
    Upload all PNG and SVG files to Wordpress host.

    Use the credentials ``cred`` and SFTP to upload all SVG and PNG images from
    the local folder ``path_html`` to the remote folder ``wp_path_img``.

    :param *dict* cred: Wordpress- and SSH credentials dictionary.
    :param *str* path_html: location of HTML file to upload.
    :param *str* wp_path_img: path to image folder on WP host.
    :param *bool* verbose: verbose output.
    :return: **None**
    """
    print('Uploading support files to {}:~/{}'.format(
        cred['ssh-login'], wp_path_img))
    
    # Create a temporary batch file with SFTP commands. SFTP has a feature
    # where all commands with a '-' prefix may silently fail.
    batch = tempfile.NamedTemporaryFile(mode='w', delete=True)
    batch.file.write('cd ' + cred['wp-path'] + '\n')
    batch.file.write('-mkdir ' + wp_path_img + '\n')
    batch.file.write('cd ' + wp_path_img + '\n')
    batch.file.write('lcd ' + "'" + path_html + "'" + '\n')
    batch.file.write('-rm *\n')
    batch.file.write('-put *\n')
    batch.file.write('bye\n')

    # We cannot close the file because that would delete it. Flush it instead
    # to ensure it contains the just added content.
    batch.file.flush()

    # Run SFTP.
    cmd = ['sftp', '-P' + str(cred['ssh-port']), '-b' + batch.name,
           cred['ssh-login']]

    if cred['ssh-key'] != '':
        cmd.insert(1, '-i' + cred['ssh-key'])

    # If 'verbose', then display all STDERR messages, otherwise don't.
    if verbose:
        print('SFTP commands:')
        print(open(batch.name, 'r').read())
        stderr = None
    else:
        stderr = subprocess.DEVNULL

    # Execute SFTP and let it read all commands from the temporary batch file.
    print('Uploading files... ', end='', flush=True)
    try:
        pout = subprocess.check_output(cmd, stderr=stderr)
    except subprocess.CalledProcessError as e:
        print('The following SFTP command did not execute properly')
        print('  ' + ' '.join(cmd))
        sys.exit(1)

    # Close the temporary batch file. This will automatically delete it.
    batch.file.close()

    # Decode the output and count how many 'Uploading' statements it contains.
    # Then tell the user how many files were uploaded.
    pout = pout.decode('utf8')
    out = [_ for _ in pout.splitlines() if 'Uploading' in _]
    print('\rAll files uploaded.')


class PostIDData():
    """
    Administrate the ``.postid`` files.

    The class is a convenience wrapper around reading and writing the .postid.
    The .postid file holds meta information that matches the HTML file to a
    particular document on the Wordpress host. The meta information consists
    of the host (eg. localhost@home), the publication type (eg. 'page' or
    'post'), and the ID assigned by Wordpress.

    :param *fname* fname: path to .postid file.
    """
    def __init__(self, fname):
        self.fname = fname
        try:
            self.fdata = open(self.fname, 'r').read()
        except FileNotFoundError as e:
            self.fdata = ''

        self.entries = self.parsePostID()

    def save(self, host, post_type, post_id):
        """
        Add new entry to .postid file.

        Raise an error unless the (``host``, ``post_type``, ``post_id``)
        combination specifies an already existing entry, or (``host``,
        ``post_type``) does not yet exists.

        This function will therefore raise an error if ``host`` and
        ``post_type`` already exists yet has a different ``post_id``. This
        usually indicates a corrupt .postid file because Wordpress never
        changes the post ID.

        :param *str* host: location of HTML file to upload.
        :param *str* post_type: path to image folder on WP host.
        :param *str* post_id: the Wordpress post ID. Use **None** to create new
          post.
        :return: **None**
        """
        data = self.savePostID(host, post_type, post_id)
        open(self.fname, 'w').write(data)

    def load(self, host, post_type):
        """
        Return .postid entry for the (``host``, ``post_type``) combination.

        Return an empty list if either no matching combination exists, or no
        .postid files exists in the first place. This case is not an error.

        This method is a wrapper around :func:`loadPostID`.

        If the `.postid` file exists and contains:

        * one match: return it,
        * One match but with different post_type: return empty list,
        * multiple matches: tell the user to specify the type.

        :param *str* host: location of HTML file to upload.
        :param *str* post_type: path to image folder on WP host.
        :param *str* post_id: the Wordpress post ID. Use **None** to create new
          post.
        :return: **None**
        """
        # Parse the .postid file for a match.
        candidates = self.loadPostID(host, post_type)

        if len(candidates) == 0:
            if post_type is None:
                # No match: complain to the user about the lacking post_type.
                msg = ('Cannot find matching entry in .postid file.\n'
                       'If this is a new post you must manually specify its '
                       'type (eg. page or post) with the --type argument.')
                raise ValueError(msg)
            else:
                # No match. However, a post_type was specified so it may
                # well be that this is going to be a new post. As such, it does
                # not yet have an ID.
                post_id = None
        elif len(candidates) == 1:
            # Found one match: extract the post ID and post type.
            candidate = candidates[0]
            post_id = candidate.ID
            post_type = candidate.type
        else:
            # Multiple matches: this may happen if the user serves up the same
            # article as both a page and a post. In this case nobby2p cannot
            # automatically determine which one to update. Complain to the
            # user.
            typelist = ', '.join([_.type for _ in candidates])
            msg = ('Error: found multiple entries for host <{}>: {}\n'
                   '       Use --type to specify which one to load.')
            msg = msg.format(candidates[0].host, typelist)
            print(msg)
            sys.exit(1)
        return post_type, post_id

    def parsePostID(self):
        """
        Return parsed content of the .postid file.

        Ignore empty lines in the .postid file.

        A valid Entry is a comma separated list of three values:

        # host name: address of Wordpress host (eg. localhost)
        # post type: usually either 'page' or 'post'
        # post ID: the ID Wordpress assigned to the post.

        :return: list of **Entry** tuples.
        """

        # Parse the data into a list of Entry tuples to simplify the
        # processing.
        entries = []
        for line in self.fdata.splitlines():
            if len(line.split(',')) == 3:
                tmp_host, tmp_type, tmp_id = line.split(',')
                entries.append(Entry(tmp_host.strip(), tmp_type.strip(),
                                     tmp_id.strip()))

        # Sanity check: all entries with the same host name and entry type are
        # unique.
        for ii in range(len(entries) - 1):
            for jj in range(ii + 1, len(entries)):
                if entries[ii].type == entries[jj].type:
                    if entries[ii].host == entries[jj].host:
                        msg = ('Corrupt .postid file: multiple entries for '
                               'same entry type and host name')
                        raise ValueError(msg)
        return entries

    def loadPostID(self, host, post_type):
        """
        Return list of matches for ``post_type`` on WP ``host``.

        The returned list will contain at most one entry if both ``host`` and
        ``post_type`` are supplied. Return all post IDs for the Wordpress
        ``host`` if ``post_type`` is **None**.

        :param *str* host: location of HTML file to upload.
        :param *str* post_type: path to image folder on WP host.
        :return: list of **Entry** tuples.
        """

        # Filter out all entries for the selected host.
        res = [_ for _ in self.entries if _.host == host]

        # Filter the post type if one was provided.
        if post_type is not None:
            res = [_ for _ in res if _.type == post_type]
            assert len(res) <= 1

        # Return the list of Entry tuples.
        return res

    def savePostID(self, host, post_type, post_id):
        """
        Add new post ID.

        Do nothing if the (``host``, ``post_type``, and ``post_id``)
        combination already exists because it means that an existing post was
        simply updated (Wordpress does not change the ID in that case).



        :param *str* host: location of HTML file to upload.
        :param *str* post_type: path to image folder on WP host.
        :return: new file content of .postid as a string.
        """
        # Ask loadPostID to provide the correct entry. If it does not return
        # any, then we add a new entry for the current type and host. If it
        # returns one we ensure it already has the correct ID. It is impossible
        # for loadPostID to return more than one option. It is a bug if it
        # does.
        existing = self.loadPostID(host, post_type)

        # Analyse the return value.
        if len(existing) == 0:
            # No matching entry: create a new one.
            self.entries.append(
                Entry(host.strip(), post_type.strip(), post_id.strip()))
        elif len(existing) == 1:
            # Matching entry: ensure its ID is the same as the supplied
            # ``post_id``.
            if existing[0].ID == post_id:
                # Nothing to add or change.
                pass
            else:
                # Not good...
                msg = ('ID mismatch for type <{}> on host <{}>. Your .postid '
                       'file is probably corrupt')
                msg = msg.format(post_type, host)
                raise ValueError(msg)
        else:
            # We should never get here.
            print('Bug')
            assert False

        # Convert the entries to a single string and return it.
        out = ''
        for e in self.entries:
            str_id = '{}, {}, {}'.format(e.host, e.type, e.ID)
            out += str_id + '\n'
        return out


def parseCmdline():
    """
    Parse the command line arguments.
    """
    # Create a parser and program description.
    parser = argparse.ArgumentParser(
        description=('Upload post and images to Wordpress'))

    # Shorthand.
    padd = parser.add_argument

    # Add the command line options.
    padd('--title', type=str, metavar='title', default=None,
         help='Set post title')
    padd('--type', type=str, metavar='type', default=None,
         help='Set post type (eg. "page" or "post")')
    padd('--cred', type=str, default='.credentials', metavar='file',
         help='Credentials file (defaults to ".credentials")')
    padd('--postid', type=str, default='.postid', metavar='file',
         help='postid file (defaults to ".postid")')
    padd('--list-posts', action='store_true', default=False,
         help='List the newest 40 posts on the selected host')
    padd('--verify', action='store_true', default=False,
         help='Test SSH- and Wordpress credentials')
    padd('-v', action='store_true', default=False,
         help='Verbose.')
    padd('file', nargs='?', help='HTML file created by Nobby.')

    # Let argparse parse the command line.
    args = parser.parse_args()

    return args


def loadHTML(fname):
    """
    Load and return the HTML file ``fname`` plus the post title, if available.

    Check if Nobby created the HTML file ``fname``. If so, the post title will
    be readily available. Complain if not, but proceed anyway (the post title
    will then be **None**).

    :param *str* fname: path to HTML file.
    :return: [html (**str**), title (**str**)]
    """
    # Load the HTML file.
    try:
        html = open(fname, 'r').read()
    except FileNotFoundError as e:
        print('Error: cannot open file')
        print(e)
        sys.exit(1)

    # Extract meta information, if available.
    tmp = html.splitlines()
    if ('nobby' in tmp[1].lower()) and ('title' in tmp[2].lower()):
        # Looks like Nobby created the file: extract the title.
        title = str(tmp[2])
        title = title.replace('Title:', '')
        title = title.strip()
    else:
        # Complain (but proceed) if the file was not created by Nobby.
        print('Does not appear to be a Nobby file.')
        title = None

    # Return the HTML code and post title.
    return html, title


def listPosts(cred):
    """
    List all posts on the selected Wordpress server.

    Log into the Wordpress server specified in ``cred`` and list the 40 most
    recent posts- and pages.

    :param *dict* cred: Wordpress- and SSH credentials dictionary.
    :return: **None**
    """
    try:
        # Connect to Wordpress.
        wp_client = wprpc.Client(cred['wp-url'] + '/xmlrpc.php',
                                 cred['wp-user'], cred['wp-pass'])

        # Retrieve all posts and pages from the Wordpress server.
        getPosts = wpmethods.posts.GetPosts
        posts = wp_client.call(getPosts({'post_type': 'post', 'number': 40}))
        pages = wp_client.call(getPosts({'post_type': 'page', 'number': 40}))

        # Create the format string.
        s = ' {0:2d} ({1}): {2}'

        # Status message.
        print('Content of Wordpress at <{}>\n'.format(cred['wp-url']))

        # Print the list of posts.
        print('Posts:')
        for idx, p in enumerate(posts):
            date = p.date.strftime('%d %b %Y %H:%M:%S')
            print(s.format(idx, date, p.title))

        # Print the list of pages.
        print('\nPages:')
        for idx, p in enumerate(pages):
            date = p.date.strftime('%d %b %Y %H:%M:%S')
            print(s.format(idx, date, p.title))
    except wprpc.exceptions.InvalidCredentialsError as e:
        # Print error message and complete set of credentials.
        print(e)
        msg = 'Wordpress credentials for host {} are wrong.'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        sys.exit(1)
    except wprpc.exceptions.ServerConnectionError as e:
        # Print error message and complete set of credentials.
        print(e)
        msg = 'Cannot connect to host {} with the following credentials'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        sys.exit(1)


def loadCredentials(cred_file):
    """
    Return the content of the ``cred_file`` as a dictionary.

    The credentials file contains the access information for the Wordpress
    RPC interface and the SSH credentials for the host it runs on. It consists
    of simple "key: value" entries. Malformed entries are ignored.

    Ignore empty lines and comments (ie. text beyond a "#" characters).

    See demo/.credentials for an explanation of the mandatory entries.

    :param *str* cred_file: path to credentials file.
    :return: dictionary with credentials.
    """
    if not os.path.exists(cred_file):
        print('Cannot find credentials file <{}> - Abort.'.format(cred_file))
        sys.exit(1)

    # Load the file.
    lines = open(cred_file, 'r').read()

    # Remove all comments.
    lines = re.sub(r'#.*', '', lines)

    # Place all key/value pairs in a dictionary.
    pat = re.compile(r'(.*?):(.*)')
    cred = {}
    for m in pat.finditer(lines):
        key, value = m.groups()
        cred[key.lower()] = value.strip()

    # Sanity checks: the credentials file must contain these keys.
    keys = set(['ssh-login', 'ssh-key', 'ssh-port', 'wp-url', 'wp-user',
                'wp-pass', 'wp-path', 'wp-img'])
    if not keys.issubset(set(cred.keys())):
        print('Credentials file <{}> misses these keys: {}'.format(
            cred_file, keys - set(cred.keys())))
        sys.exit(1)
    return cred


def verifyCredentials(cred):
    """
    Verify the Wordpress- and SSH credentials.

    Connect to the Wordpress instance via its RPC interface, and to the
    Wordpress host via SSH/SFTP.

    Print a message if an error occurs and quit.

    For the Wordpress test:

    # Log into Wordpress.
    # Query available posts.

    For SSH/SFTP test:

    # Connect to Wordpress host via SFTP,
    # change into the specified Wordpress directory,
    # change into the specified image directory,
    # create a temporary directory there,
    # delete said temporary directory,
    # exit.

    :param *dict* cred: Wordpress- and SSH credentials dictionary.
    """
    # ----------------------------------------------------------------------
    #                      Check Wordpress Credentials
    # ----------------------------------------------------------------------
    try:
        # Connect to Wordpress.
        wp_client = wprpc.Client(cred['wp-url'] + '/xmlrpc.php',
                                 cred['wp-user'], cred['wp-pass'])

        # Query some posts (ignore result).
        getPosts = wpmethods.posts.GetPosts
        posts = wp_client.call(getPosts({'post_type': 'post'}))
    except wprpc.exceptions.InvalidCredentialsError as e:
        # Print error message and complete set of credentials.
        print('Wordpress:  Error')
        print('-' * 75)
        print(e)
        msg = 'Wordpress credentials for host {} are wrong.'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        print('-' * 75)
        sys.exit(1)
    except wprpc.exceptions.ServerConnectionError as e:
        # Print error message and complete set of credentials.
        print('Wordpress:  Error')
        print('-' * 75)
        print(e)
        msg = 'Cannot connect to host {} with the following credentials'
        print(msg.format(cred['wp-url']))
        for key in sorted(cred):
            print('    ' + str(key) + ': ' + str(cred[key]))
        print('-' * 75)
        sys.exit(1)
    print('Wordpress:  Ok')

    # ----------------------------------------------------------------------
    #                        Check SSH Credentials
    # ----------------------------------------------------------------------
    # Create a temporary batch file for SFTP.
    test_dir = 'nobby_test_dir_ignore_me_and_delete_me'
    batch = tempfile.NamedTemporaryFile(mode='w', delete=True)
    batch.file.write('cd ' + cred['wp-path'] + '\n')
    batch.file.write('cd ' + cred['wp-img'] + '\n')
    batch.file.write('mkdir ' + test_dir + '\n')
    batch.file.write('rmdir ' + test_dir + '\n')
    batch.file.write('bye\n')
    batch.file.flush()

    # Run SFTP.
    cmd = ['sftp', '-P' + str(cred['ssh-port']), '-b' + batch.name,
           cred['ssh-login']]

    if cred['ssh-key'] != '':
        cmd.insert(1, '-i' + cred['ssh-key'])

    # Execute SFTP and let it read all commands from the temporary batch file.
    try:
        pout = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        print('SSH access: Failed')
        print('-' * 75)
        print('<' + ' '.join(cmd) + '>\n')
        print('SFTP commands:')
        print(open(batch.name, 'r').read().strip())
        print('-' * 75)
        sys.exit(1)
    print('SSH access: Ok')

    # Close the temporary batch file. This will automatically delete it.
    batch.file.close()


def main():
    # Parse command line and verify the input is proper.
    param = parseCmdline()

    # Load the SSH- and Wordpress credentials.
    cred = loadCredentials(param.cred)

    if param.verify:
        # Ensure the credentials are correct.
        verifyCredentials(cred)
        sys.exit(0)

    if param.list_posts:
        # List all Wordpress posts.
        listPosts(cred)
        sys.exit(0)

    if param.file is None:
        print('Missing argument. Use -h for help')
        sys.exit(1)
    else:
        path_html, file_html = os.path.split(param.file)

    # Load the HTML file.
    html, post_title = loadHTML(param.file)

    post_id_data = PostIDData(param.postid)
    try:
        post_type, post_id = post_id_data.load(cred['ssh-login'], param.type)
    except ValueError as e:
        print('Error: postID')
        print(e)
        sys.exit(1)

    # If the .postid file does not yet contain an ID for this post then create
    # a new (empty) post in Wordpress to obtain the next available post_id.
    if post_id is None:
        post_id = updatePost(cred, None, post_type, post_title, '')

    # The path for the SVG- and PNG images on the WP host depends on the MD5
    # hash of the post ID. This ID is already unique; the MD5 hash is thus only
    # for show :)
    tmp = hashlib.md5(str(post_id).encode('utf8')).hexdigest()
    wp_path_img = os.path.join(cred['wp-img'], tmp[:6])
    del tmp

    # Update image paths to their new location on the Wordpress host.
    tmp = os.path.join(cred['wp-url'], wp_path_img)
    post_content = updateImageTags(html, tmp)
    del tmp

    # Upload the post to Wordpress.
    post_id = updatePost(cred, post_id, post_type, post_title, post_content)

    # Update the Wordpress ID file. Its content will not change if it already
    # exists and contains a valid ID, because that ID will have been used for
    # updating the post.
    post_id_data.save(cred['ssh-login'], post_type, post_id)

    # Copy all SVG and PNG images via SFTP to the Wordpress host.
    copyImageFiles(cred, path_html, wp_path_img, param.v)


if __name__ == '__main__':
    main()
