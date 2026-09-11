package main

import (
	"context"
	"fmt"
	"sync"
)

type Task struct {
	ID   int
	Work func() (string, error)
}

type Result struct {
	TaskID int
	Output string
	Err    error
}

func WorkerPool(ctx context.Context, numWorkers int, tasks <-chan Task, results chan<- Result) {
	var wg sync.WaitGroup

	for i := 1; i <= numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for task := range tasks {
				select {
				case <-ctx.Done():
					results <- Result{TaskID: task.ID, Err: ctx.Err()}
					return
				default:
					out, err := task.Work()
					results <- Result{TaskID: task.ID, Output: out, Err: err}
				}
			}
		}(i)
	}

	wg.Wait()
	close(results)
}