""" Define the routes that show all the posts.

This includes:
  - /feed
  - /cluster
  - /table
  - /favorites
"""
import os
from flask import request, render_template, redirect, Blueprint, current_app
from sqlalchemy import and_, or_

from ..app import db_session
from ..utils.posts import get_posts
from ..models import Post, Tag, User, PageView
from ..utils.requests import from_request_get_feed_params
from ..utils.render import render_post_tldr

blueprint = Blueprint(
    'index', __name__, template_folder='../templates', static_folder='../static')


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


@blueprint.route("/site-map")
@PageView.log_pageview
def site_map():
    links = []
    for rule in current_app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        # if "GET" in rule.methods and has_no_empty_params(rule):
        # url = url_for(rule.endpoint, **(rule.defaults or {}))
        links.append((str(rule), rule.endpoint))
    # links is now a list of url, endpoint tuples
    return '<br />'.join(str(link) for link in links)


@blueprint.route('/')
@PageView.log_pageview
def render_index():
    return redirect('/feed')


@blueprint.route('/favorites')
@PageView.log_pageview
def render_favorites():
    """ Renders the index-feed view for posts that are liked """

    feed_params = from_request_get_feed_params(request)
    user_id = feed_params['user_id']

    user = (db_session.query(User)
            .filter(User.id == user_id)
            .first())
    posts = user.get_liked_posts

    post_stats = {post.path: {'all_views': post.view_count,
                              'distinct_views': post.view_user_count,
                              'total_likes': post.vote_count,
                              'total_comments': post.comment_count} for post in posts}
    # Post.authors is lazy loaded, so we need to make sure it has been loaded before being
    # passed beyond the scope of this database db_session.
    for post in posts:
        post.authors
    db_session.close()

    return render_template("index-feed.html",
                           feed_params=feed_params,
                           posts=posts,
                           post_stats=post_stats,
                           top_header='Favorites',
                           contribs=current_app.config['plugins'])


@blueprint.route('/feed')
@PageView.log_pageview
def render_feed():
    """ Renders the index-feed view """
    feed_params = from_request_get_feed_params(request)
    posts, post_stats = get_posts(feed_params)
    for post in posts:
        post.tldr = render_post_tldr(post)

    return render_template("index-feed.html",
                           feed_params=feed_params,
                           posts=posts,
                           post_stats=post_stats,
                           top_header='Knowledge Feed',
                           contribs=current_app.config['plugins'])


@blueprint.route('/table')
@PageView.log_pageview
def render_table():
    """Renders the index-table view"""
    feed_params = from_request_get_feed_params(request)
    posts, post_stats = get_posts(feed_params)
    # TODO reference stats inside the template
    return render_template("index-table.html",
                           posts=posts,
                           post_stats=post_stats,
                           top_header="Knowledge Table",
                           feed_params=feed_params,
                           contribs=current_app.config['plugins'])


@blueprint.route('/cluster')
@PageView.log_pageview
def render_cluster():
    """ Render the cluster view """
    # we don't use the from_request_get_feed_params because some of the
    # defaults are different
    filters = request.args.get('filters', '')
    sort_by = request.args.get('sort_by', 'alpha')
    group_by = request.args.get('group_by', 'folder')
    request_tag = request.args.get('tag')
    sort_desc = not bool(request.args.get('sort_asc', ''))

    post_query = db_session.query(Post).filter(Post.is_published)

    if filters:
        filter_set = filters.split(" ")
        for elem in filter_set:
            elem_regexp = "%," + elem + ",%"
            post_query = post_query.filter(Post.keywords.like(elem_regexp))

    if group_by == "author":
        author_to_posts = {}
        authors = (db_session.query(User).all())
        for author in authors:
            author_posts = [post for post in author.posts if post.is_published]
            if author_posts:
                author_to_posts[author.format_name] = author_posts
        tuples = [(k, v) for (k, v) in author_to_posts.iteritems()]

    elif group_by == "tags":
        tags_to_posts = {}
        all_tags = (db_session.query(Tag).all())

        for tag in all_tags:
            tag_posts = [post for post in tag.posts if post.is_published]
            if tag_posts:
                tags_to_posts[tag.name] = tag.posts
        tuples = [(k, v) for (k, v) in tags_to_posts.iteritems()]

    elif group_by == "folder":
        posts = post_query.all()
        # group by folder
        folder_to_posts = {}

        for post in posts:
            folder = os.path.dirname(post.path)
            if folder in folder_to_posts:
                folder_to_posts[folder].append(post)
            else:
                folder_to_posts[folder] = [post]

        tuples = [(k, v) for (k, v) in folder_to_posts.iteritems()]

    else:
        raise ValueError("Group by `{}` not understood.".format(group_by))

    if sort_by == 'alpha':
        grouped_data = sorted(tuples, key=lambda x: x[0])
    else:
        grouped_data = sorted(
            tuples, key=lambda x: len(x[1]), reverse=sort_desc)

    db_session.close()

    return render_template("index-cluster.html",
                           grouped_data=grouped_data,
                           filters=filters,
                           sort_by=sort_by,
                           group_by=group_by,
                           tag=request_tag,
                           contribs=current_app.config['plugins'])
