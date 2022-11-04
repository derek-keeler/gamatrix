import React from 'react';

class UserSelect extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            error: null,
            isLoaded: false,
            items: []
        };
    }
    componentDidMount() {
        fetch("/api_1_0/users")
            .then(res => res.json())
            .then(
                (result) => {
                    this.setState({
                        isLoaded: true,
                        items: result.items
                    });
                },
                (error) => {
                    this.setState({
                        isLoaded: true,
                        error
                    });
                }
            )
    }
    render() {
        const { error, isLoaded, items } = this.state
        if (error) {
            return <div>Error: {error.message}</div>;
        } else if (!isLoaded) {
            return <div>Loading...</div>;
        } else {
            return (
                <div id="user-selector-component">
                    <input type="checkbox" id="{{ users[user]['username'] }}" name="{{ user }}" checked><a
                        href="" style="text-decoration: none"
                        title="DB date: {{ users[user]['db_mtime'] }}">
                        <label for="{{ users[user]['username'] }}"><img
                            src="/static/profile_img/{{ users[user]['pic']|default('question_block.jpg') }}"
                            width="20" height="20"> {{ users[user]['username'] }}
                        </label></a>
                    </input>
                </div>
            )
        }
    }
}
