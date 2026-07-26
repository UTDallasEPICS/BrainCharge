import { Component } from "react";

export default class CalendarErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="calendar-screen">
          <div className="calendar-header">
            <h1>Calendar</h1>
            <p>We couldn&apos;t load the calendar view.</p>
          </div>
          <div className="calendar-error">
            <p>{this.state.error.message || "Something went wrong."}</p>
            <button
              type="button"
              className="retry-btn"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
