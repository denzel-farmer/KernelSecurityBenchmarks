
# Copy the figures from the results dir to the figs dir 
FIGS_TO_COPY=(
    "cos_bar.png"
    "fork_bin_sh_bar.png"
    "fork_execve_bar.png"
    "fork_exit_bar.png"
    "fstat_bar.png"
    "open_close_bar.png"
    "pipe_latency_bar.png"
    "pthread_once_bar.png"
    "read_bar.png"
    "select_500_bar.png"
    "stat_bar.png"
    "syscall_bar.png"
    "unix_sock_stream_latency_bar.png"
    "write_bar.png"
)

RESULTS_DIR="/home/john/Senior/HardwareSecurity/final-project/NewSecBench/KernelSecurityBenchmark/kernsecbench/results-analysis/figs"
FIGS_DIR="/home/john/Senior/HardwareSecurity/final-project/NewSecBench/documentation/figs"

# Create the figs dir if it doesn't exist
mkdir -p $FIGS_DIR
# Copy the figures from the results dir to the figs dir
for fig in "${FIGS_TO_COPY[@]}"; do
    cp $RESULTS_DIR/$fig $FIGS_DIR/
done